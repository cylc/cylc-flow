# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Functionality for selecting a host from pre-defined list."""
import ast
from collections import namedtuple
from functools import lru_cache
from io import BytesIO
import json
import random
from time import sleep
import token
from tokenize import tokenize

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import CylcError, HostSelectException
from cylc.flow.hostuserutil import get_fqdn_by_host, is_remote_host
from cylc.flow.remote import run_cmd, cylc_server_cmd
from cylc.flow.terminal import parse_dirty_json


def select_workflow_host(cached=True):
    """Return a host as specified in `[workflow hosts]`.

    * Condemned hosts are filtered out.
    * Filters out hosts excluded by ranking (if defined).
    * Ranks by ranking (if defined).

    Args:
        cached (bool):
            Use a cached version of the global configuration if True
            else reload from the filesystem.

    Returns:
        tuple - See `select_host` for details.

    Raises:
        HostSelectException:
            See `select_host` for details.
        socket.gaierror:
            See `select_host` for details.

    """
    # get the global config, if cached = False a new config instance will
    # be returned with the up-to-date configuration.
    global_config = glbl_cfg(cached=cached)

    return select_host(
        # list of workflow hosts
        global_config.get([
            'scheduler', 'run hosts', 'available'
        ]) or ['localhost'],
        # rankings to apply
        ranking_string=global_config.get([
            'scheduler', 'run hosts', 'ranking'
        ]),
        # list of condemned hosts
        blacklist=global_config.get(
            ['scheduler', 'run hosts', 'condemned']
        ),
        blacklist_name='condemned host'
    )


def select_host(
        hosts,
        ranking_string=None,
        blacklist=None,
        blacklist_name=None
):
    """Select a host from the provided list.

    If no ranking is provided (in `ranking_string`) then random selection
    is used.

    Args:
        hosts (list):
            List of host names to choose from.
            NOTE: Host names must be identifiable from the host where the
            call is executed.
        ranking_string (str):
            A multiline string containing Python expressions to filter
            hosts by e.g::

               # only consider hosts with less than 70% cpu usage
               # and a server load of less than 5
               cpu_percent() < 70
               getloadavg()[0] < 5

            And or Python statements to rank hosts by e.g::

               # rank by used cpu, then by load average as a tie-break
               # (lower scores are better)
               cpu_percent()
               getloadavg()

            Comments are allowed using `#` but not inline comments.
        blacklist (list):
            List of host names to filter out.
            Can be short host names (do not have to be fqdn values)
        blacklist_name (str):
            The reason for blacklisting these hosts
            (used for exceptions).

    Raises:
        HostSelectException:
            In the event that no hosts are available / meet the specified
            criterion.
        socket.gaierror:
            This may be raised in the event of unknown host names
            for some installations or not for others.

    Returns:
        tuple - (hostname, fqdn) the chosen host

        hostname (str):
            The hostname as provided to this function.
        fqdn (str):
            The fully qualified domain name of this host.

    """
    # standardise host names - remove duplicate items
    hostname_map = {  # note dictionary keys filter out duplicates
        get_fqdn_by_host(host): host
        for host in hosts
    }
    hosts = list(hostname_map)
    if blacklist:
        blacklist = list(set(map(get_fqdn_by_host, blacklist)))

    # dict of conditions and whether they have been met (for error reporting)
    data = {
        host: {}
        for host in hosts
    }

    # filter out `filter_hosts` if provided
    if blacklist:
        hosts, data = _filter_by_hostname(
            hosts,
            blacklist,
            blacklist_name,
            data=data
        )

    if not hosts:
        # no hosts provided / left after filtering
        raise HostSelectException(data)

    rankings = []
    if ranking_string:
        # parse rankings
        rankings = list(_get_rankings(ranking_string))

    if not rankings:
        # no metrics or ranking required, pick host at random
        hosts = [random.choice(list(hosts))]  # nosec

    if not rankings and len(hosts) == 1:
        return hostname_map[hosts[0]], hosts[0]

    # filter and sort by rankings
    metrics = list({x for x, _ in rankings})  # required metrics
    results, data = _get_metrics(  # get data from each host
        hosts, metrics, data)
    hosts = list(results)  # some hosts might not be contactable

    # stop here if we don't need to proceed
    if not hosts:
        # no hosts provided / left after filtering
        raise HostSelectException(data)
    if not rankings and len(hosts) == 1:
        return hostname_map[hosts[0]], hosts[0]

    hosts, data = _filter_by_ranking(
        # filter by rankings, sort by ranking
        hosts,
        rankings,
        results,
        data=data
    )

    if not hosts:
        # no hosts provided / left after filtering
        raise HostSelectException(data)

    return hostname_map[hosts[0]], hosts[0]


def _filter_by_hostname(
        hosts,
        blacklist,
        blacklist_name=None,
        data=None
):
    """Filter out any hosts present in `blacklist`.

    Args:
        hosts (list):
            List of host fqdns.
        blacklist (list):
            List of blacklisted host fqdns.
        blacklist_name (str):
            The reason for blacklisting these hosts
            (used for exceptions).
        data (dict):
            Dict of the form {host: {}}
            (used for exceptions).

    Examples
        >>> _filter_by_hostname(['a'], [], 'meh')
        (['a'], {'a': {'blacklisted(meh)': False}})
        >>> _filter_by_hostname(['a', 'b'], ['a'])
        (['b'], {'a': {'blacklisted': True}, 'b': {'blacklisted': False}})

    """
    if not data:
        data = {host: {} for host in hosts}
    for host in list(hosts):
        key = 'blacklisted'
        if blacklist_name:
            key = f'{key}({blacklist_name})'
        if host in blacklist:
            hosts.remove(host)
            data[host][key] = True
        else:
            data[host][key] = False
    return hosts, data


def _filter_by_ranking(hosts, rankings, results, data=None):
    """Filter and rank by the provided rankings.

    Args:
        hosts (list):
            List of host fqdns.
        rankings (list):
            Thresholds which must be met.
            List of rankings as returned by `get_rankings`.
        results (dict):
            Nested dictionary as returned by `get_metrics` of the form:
            `{host: {value: result, ...}, ...}`.
        data (dict):
            Dict of the form {host: {}}
            (used for exceptions).

    Examples:
        # ranking
        >>> _filter_by_ranking(
        ...     ['a', 'b'],
        ...     [('X', 'RESULT')],
        ...     {'a': {'X': 123}, 'b': {'X': 234}}
        ... )
        (['a', 'b'], {'a': {}, 'b': {}})

        # rankings
        >>> _filter_by_ranking(
        ...     ['a', 'b'],
        ...     [('X', 'RESULT < 200')],
        ...     {'a': {'X': 123}, 'b': {'X': 234}}
        ... )
        (['a'], {'a': {'X() < 200': True}, 'b': {'X() < 200': False}})

        # no matching hosts
        >>> _filter_by_ranking(
        ...     ['a'],
        ...     [('X', 'RESULT > 1')],
        ...     {'a': {'X': 0}}
        ... )
        ([], {'a': {'X() > 1': False}})

    """
    if not data:
        data = {host: {} for host in hosts}
    good = []
    for host in hosts:
        host_rankings = {}
        host_rank = []
        for key, expression in rankings:
            item = _reformat_expr(key, expression)
            result = _simple_eval(expression, RESULT=results[host][key])
            if isinstance(result, bool):
                host_rankings[item] = result
                data[host][item] = result
            else:
                host_rank.append(result)
        if all(host_rankings.values()):
            good.append((host_rank, host))

    if not good:
        pass
    elif good[0][0]:
        # there is a ranking to sort by, use it
        good.sort()
    else:
        # no ranking, randomise
        random.shuffle(good)

    return (
        # list of all hosts which passed rankings (sorted by ranking)
        [host for _, host in good],
        # data
        data
    )


class SimpleVisitor(ast.NodeVisitor):
    """Abstract syntax tree node visitor for simple safe operations."""

    def visit(self, node):
        if not isinstance(node, self.whitelist):
            # permit only whitelisted operations
            raise ValueError(type(node))
        return super().visit(node)

    whitelist = (
        ast.Expression,
        # variables
        ast.Name, ast.Load, ast.Attribute, ast.Subscript, ast.Index,
        # opers
        ast.BinOp, ast.operator,
        # types
        ast.Num, ast.Str,
        # comparisons
        ast.Compare, ast.cmpop, ast.List, ast.Tuple
    )


def _simple_eval(expr, **variables):
    """Safely evaluates simple python expressions.

    Supports a minimal subset of Python operators:
    * Binary operations
    * Simple comparisons

    Supports a minimal subset of Python data types:
    * Numbers
    * Strings
    * Tuples
    * Lists

    Examples:
        >>> _simple_eval('1 + 1')
        2
        >>> _simple_eval('1 < a', a=2)
        True
        >>> _simple_eval('1 in (1, 2, 3)')
        True
        >>> import psutil
        >>> _simple_eval('a.available > 0', a=psutil.virtual_memory())
        True

        If you try to get it to do something you're not allowed to:
        >>> _simple_eval('open("foo")')
        Traceback (most recent call last):
        CylcError: Invalid expression: open("foo")

        If you try to do something which doesn't make sense:
        >>> _simple_eval('a.b.c')  # no value "a.b.c"
        Traceback (most recent call last):
        CylcError: Invalid expression: a.b.c

    """
    try:
        node = ast.parse(expr.strip(), mode='eval')
        SimpleVisitor().visit(node)
        # acceptable use of eval due to restricted language features
        return eval(  # nosec
            compile(node, '<string>', 'eval'),
            {'__builtins__': None},
            variables
        )
    except Exception as exc:
        raise CylcError(f'Invalid expression: {expr}\n{exc}')


def _get_rankings(string):
    """Yield parsed ranking expressions.

    Examples:
        The first ``token.NAME`` encountered is returned as the query:
        >>> _get_rankings('foo() == 123').__next__()
        (('foo',), 'RESULT == 123')

        If multiple are present they will not get parsed:
        >>> _get_rankings('foo() in bar()').__next__()
        (('foo',), 'RESULT in bar()')

        Positional arguments are added to the query tuple:
        >>> _get_rankings('1 in foo("a")').__next__()
        (('foo', 'a'), '1 in RESULT')

        Comments (not in-line) and multi-line strings are permitted:
        >>> _get_rankings('''
        ...     # earl of sandwhich
        ...     foo() == 123
        ...     # beef wellington
        ... ''').__next__()
        (('foo',), 'RESULT == 123')

    Yields:
        tuple - (query, expression)
        query (tuple):
            The method to call followed by any positional arguments.
        expression (str):
            The expression with the method call replaced by `RESULT`

    """
    for line in string.splitlines():
        # parse the string one line at a time
        # purposefully don't support multi-line expressions
        line = line.strip()

        if not line or line.startswith('#'):
            # skip blank lines
            continue

        query = []
        start = None
        in_args = False

        line_feed = BytesIO(line.encode())
        for item in tokenize(line_feed.readline):
            if item.type == token.ENCODING:
                # encoding tag, not of interest
                pass
            elif not query:
                # the first token.NAME has not yet been encountered
                if item.type == token.NAME and item.string != 'in':
                    # this is the first token.NAME, assume it it the method
                    start = item.start[1]
                    query.append(item.string)
            elif item.string == '(':
                # positional arguments follow this
                in_args = True
            elif item.string == ')':
                # end of positional arguments
                in_args = False
                break
            elif in_args:
                # literal eval each argument
                query.append(ast.literal_eval(item.string))
        end = item.end[1]

        yield (
            tuple(query),
            line[:start] + 'RESULT' + line[end:]
        )


@lru_cache()
def _tuple_factory(name, params):
    """Wrapper to namedtuple which caches results to prevent duplicates."""
    return namedtuple(name, params)


def _deserialise(metrics, data):
    """Convert dict to named tuples.

    Examples:
        >>> _deserialise(
        ...     [
        ...         ['foo', 'bar'],
        ...         ['baz']
        ...     ],
        ...     [
        ...         {'a': 1, 'b': 2, 'c': 3},
        ...         [1, 2, 3]
        ...     ]
        ... )
        [foo(a=1, b=2, c=3), [1, 2, 3]]

    """
    for index, (metric, datum) in enumerate(zip(metrics, data)):
        if isinstance(datum, dict):
            data[index] = _tuple_factory(
                metric[0],
                tuple(datum.keys())
            )(
                *datum.values()
            )
    return data


def _get_metrics(hosts, metrics, data=None):
    """Retrieve host metrics using SSH if necessary.

    Note hosts will not appear in the returned results if:
    * They are not contactable.
    * There is an error in the command which returns the results.

    Args:
        hosts (list):
            List of host fqdns.
        metrics (list):
            List in the form [(function, arg1, arg2, ...), ...]
        data (dict):
            Used for logging success/fail outcomes of the form {host: {}}

    Examples:
        Command failure:
        >>> _get_metrics(['localhost'], [['elephant']])
        ({}, {'localhost': {'get_metrics': 'Command failed (exit: 1)'}})

    Returns:
        dict - {host: {(function, arg1, arg2, ...): result}}

    """
    host_stats = {}
    proc_map = {}
    if not data:
        data = {host: {} for host in hosts}

    # Start up commands on hosts
    cmd = ['psutil']
    kwargs = {
        'stdin_str': json.dumps(metrics),
        'capture_process': True
    }
    for host in hosts:
        if is_remote_host(host):
            proc_map[host] = cylc_server_cmd(cmd, host=host, **kwargs)
        else:
            proc_map[host] = run_cmd(['cylc'] + cmd, **kwargs)

    # Collect results from commands
    while proc_map:
        for host, proc in list(proc_map.copy().items()):
            if proc.poll() is None:
                continue
            del proc_map[host]
            out, err = (f.decode() for f in proc.communicate())
            if proc.wait():
                # Command failed in verbose/debug mode
                LOG.warning(
                    'Could not evaluate "%s" (return code %d)\n%s',
                    host, proc.returncode, err
                )
                data[host]['get_metrics'] = (
                    f'Command failed (exit: {proc.returncode})')
            else:
                host_stats[host] = dict(zip(
                    metrics,
                    # convert JSON dicts -> namedtuples
                    _deserialise(metrics, parse_dirty_json(out))
                ))
        sleep(0.01)
    return host_stats, data


def _reformat_expr(key, expression):
    """Convert a ranking tuple back into an expression.

    Examples:
        >>> ranking = 'a().b < c'
        >>> _reformat_expr(
        ...     *[x for x in _get_rankings(ranking)][0]
        ... ) == ranking
        True

    """
    return expression.replace(
        'RESULT',
        f'{key[0]}({", ".join(map(repr, key[1:]))})'
    )
