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

from functools import partial
from subprocess import Popen, PIPE

from packaging.specifiers import SpecifierSet

from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    WorkflowStopped,
)
from cylc.flow.network.client_factory import get_client
from cylc.flow.id import Tokens
from cylc.flow.tui.util import (
    extract_context
)


# the GraphQL query which Tui runs against each of the workflows
# is is subscribed to
_QUERY = '''
  query cli($taskStates: [String]){
    workflows {
      id
      name
      port
      status
      stateTotals
      taskProxies(states: $taskStates) {
        id
        name
        cyclePoint
        state
        isHeld
        isQueued
        isRunahead
        isRetry
        isWallclock
        isXtriggered
        flowNums
        firstParent {
          id
          name
        }
        jobs(sort: { keys: ["submit_num"], reverse: true}) {
          id
          submitNum
          state
          platform
          jobRunnerName
          jobId
          startedTime
          estimatedFinishTime
          finishedTime
        }
        task {
          meanElapsedTime
        }
      }
      familyProxies(exids: ["*/root"]) {
        id
        name
        cyclePoint
        state
        isHeld
        isQueued
        isRunahead
        isRetry
        isWallclock
        isXtriggered
        firstParent {
          id
          name
        }
      }
      cyclePoints: familyProxies(ids: ["*/root"]) {
        id
        name
        cyclePoint
        state
        isHeld
        isQueued
        isRunahead
        isRetry
        isWallclock
        isXtriggered
        firstParent {
          id
          name
        }
      }
    }
  }
'''


# graphql queries for every version of Cylc that Tui supports:
_COMPAT_QUERIES = (
    (
        # regular query for current and future scheduler versions
        SpecifierSet('>=8.6.dev'), _QUERY
    ),
    (
        # BACK COMPAT
        # estimatedFinishTime field added at 8.6.0
        SpecifierSet('>=8.5.0, <8.6'),
        _QUERY.replace('estimatedFinishTime', '')
    ),
    (
        # BACK COMPAT
        # isRetry, isWallclock and isXtriggered fields added at 8.5.0
        SpecifierSet('>=8, <8.5'),
        _QUERY
        .replace('isRetry', '')
        .replace('isWallclock', '')
        .replace('isXtriggered', '')
        .replace('estimatedFinishTime', ''),
    ),
)


# the list of mutations we can call on a running scheduler
MUTATIONS = {
    'workflow': [
        'pause',
        'reload',
        'stop',
    ],
    'cycle': [
        'hold',
        'release',
        'kill',
        'trigger',
        'poll',
    ],
    'task': [
        'hold',
        'release',
        'kill',
        'trigger',
        'poll',
        'set',
        'remove',
    ],
    'job': [
        'kill',
    ]
}

# mapping of Tui's node types (e.g. workflow) onto GraphQL argument types
# (e.g. WorkflowID)
ARGUMENT_TYPES = {
    # <tui-node-type>: <graphql-argument-type>
    'workflow': '[WorkflowID]!',
    'task': '[NamespaceIDGlob]!',
}


class VersionIncompat(Exception):
    ...


def get_query(scheduler_version: str) -> str:
    """Return a GraphQL query compatibile with the provided scheduler version.

    Args:
        scheduler_version: The version of the scheduler we are connecting to.

    Returns:
        The GraphQL query string.

    Raises:
        VersionIncompat:
            If the scheduler version is not supported.

    """
    for query_version_range, query in _COMPAT_QUERIES:
        if scheduler_version in query_version_range:
            return query
    raise VersionIncompat(
        f'Scheduler version {scheduler_version} is not supported'
    )


def cli_cmd(*cmd, ret=False):
    """Issue a CLI command.

    Args:
        cmd:
            The command without the 'cylc' prefix'.
        ret:
            If True, the stdout will be returned.

    Rasies:
        ClientError:
            In the event of mishap for consistency with the network
            client alternative.

    """
    proc = Popen(  # nosec (command constructed internally, no untrusted input)
        ['cylc', *cmd],
        stderr=PIPE,
        stdout=PIPE,
        text=True,
    )
    _out, err = proc.communicate()
    if proc.returncode != 0:
        raise ClientError(f'Error in command cylc {" ".join(cmd)}\n{err}')
    if ret:
        return _out


def _show(id_):
    """Special mutation to display cylc show output."""
    # dynamic import to avoid circular import issues
    from cylc.flow.tui.overlay import text_box
    return partial(
        text_box,
        text=cli_cmd('show', id_, '--color=never', ret=True),
    )


def _log(id_):
    """Special mutation to open the log view."""
    # dynamic import to avoid circular import issues
    from cylc.flow.tui.overlay import log
    return partial(
        log,
        id_=id_,
        list_files=partial(_list_log_files, id_),
        get_log=partial(_get_log, id_),
    )


def _parse_log_header(contents):
    """Parse the cat-log header.

    The "--prepend-path" option to "cat-log" adds a line containing the host
    and path to the file being viewed in the form:

        # <host>:<path>

    Args:
        contents:
            The raw log file contents as returned by "cat-log".

    Returns:
        tuple - (host, path, text)

        host:
            The host where the file was retrieved from.
        path:
            The absolute path to the log file.
        text:
            The log file contents with the header removed.

    """
    contents, text = contents.split('\n', 1)
    contents = contents.replace('# ', '')
    host, path = contents.split(':')
    return host, path, text


def _get_log(id_, filename=None):
    """Retrieve the contents of a log file.

    Args:
        id_:
            The Cylc universal ID of the thing you want to fetch the log file
            for.
        filename:
            The file name to retrieve (note name not path).
            If "None", then the default log file will be retrieved.

    """
    cmd = [
        'cat-log',
        '--mode=cat',
        '--prepend-path',
    ]
    if filename:
        cmd.append(f'--file={filename}')
    text = cli_cmd(
        *cmd,
        id_,
        ret=True,
    )
    return _parse_log_header(text)


def _list_log_files(id_):
    """Return a list of available log files.

    Args:
        id_:
            The Cylc universal ID of the thing you want to fetch the log file
            for.

    """
    text = cli_cmd('cat-log', '--mode=list-dir', id_, ret=True)
    return text.splitlines()


# the mutations we have to go through the CLI to perform
OFFLINE_MUTATIONS = {
    'user': {
        'stop-all': partial(cli_cmd, 'stop', '*'),
    },
    'workflow': {
        'play': partial(cli_cmd, 'play'),
        'clean': partial(cli_cmd, 'clean', '--yes'),
        'reinstall-reload': partial(cli_cmd, 'vr', '--yes'),
        'log': _log,
    },
    'task': {
        'log': _log,
        'show': _show,
    },
    'job': {
        'log': _log,
    },
}


def generate_mutation(mutation, arguments):
    """Return a GraphQL mutation string.

    Args:
        mutation:
            The mutation name.
        Arguments:
            The arguments to provide to it.

    """
    arguments.pop('user')
    graphql_args = ', '.join([
        f'${argument}: {ARGUMENT_TYPES[argument]}'
        for argument in arguments
    ])
    mutation_args = ', '.join([
        f'{argument}s: ${argument}'
        for argument in arguments
    ])

    return f'''
        mutation({graphql_args}) {{
            {mutation} ({mutation_args}) {{
                result
            }}
        }}
    '''


def list_mutations(selection, is_running=True):
    """List mutations relevant to the provided selection.

    Args:
        selection:
            The user selection.
        is_running:
            If False, then mutations which require the scheduler to be
            running will be omitted.

            Note, this is only relevant for workflow nodes because if a
            workflow is stopped, then any tasks within it will be removed
            anyway.

    """
    context = extract_context(selection)
    selection_type = list(context)[-1]
    ret = []
    if is_running:
        # add the online mutations
        ret.extend(MUTATIONS.get(selection_type, []))
    # add the offline mutations
    ret.extend(OFFLINE_MUTATIONS.get(selection_type, []))
    return sorted(ret)


def context_to_variables(context, jobs=False):
    """Derive multiple selection out of single selection.

    Note, this interface exists with the aim of facilitating the addition of
    multiple selection at a later date.

    Examples:
        >>> context_to_variables(extract_context(['~a/b//c/d']))
        {'user': ['a'], 'workflow': ['b'], 'task': ['c/d']}

        >>> context_to_variables(extract_context(['~a/b//c']))
        {'user': ['a'], 'workflow': ['b'], 'task': ['c/*']}

        >>> context_to_variables(extract_context(['~a/b']))
        {'user': ['a'], 'workflow': ['b']}

        # Note, jobs are omitted by default
        >>> context_to_variables(extract_context(['~a/b//c/d/01']))
        {'user': ['a'], 'workflow': ['b'], 'task': ['c/d']}

        # This is because Cylc commands cannot generally operate on jobs only
        # tasks.
        # To let jobs slide through:
        >>> context_to_variables(extract_context(['~a/b//c/d/01']), jobs=True)
        {'user': ['a'], 'workflow': ['b'], 'job': ['c/d/01']}

    """
    # context_to_variables because it can only handle single-selection ATM
    variables = {'user': context['user']}

    if 'workflow' in context:
        variables['workflow'] = context['workflow']
    if jobs and 'job' in context:
        variables['job'] = [
            Tokens(
                cycle=context['cycle'][0],
                task=context['task'][0],
                job=context['job'][0],
            ).relative_id
        ]
    elif 'task' in context:
        variables['task'] = [
            Tokens(
                cycle=context['cycle'][0],
                task=context['task'][0]
            ).relative_id
        ]
    elif 'cycle' in context:
        variables['task'] = [
            Tokens(cycle=context['cycle'][0], task='*').relative_id
        ]
    return variables


def mutate(mutation, selection):
    """Call a mutation.

    Args:
        mutation:
            The mutation name (e.g. stop).
        selection:
            The Tui selection (i.e. the row(s) selected in Tui).

    """
    if mutation in {
        _mutation
        for section in OFFLINE_MUTATIONS.values()
        for _mutation in section
    }:
        return offline_mutate(mutation, selection)
    else:
        online_mutate(mutation, selection)
    return None


def online_mutate(mutation, selection):
    """Issue a mutation over a network interface."""
    context = extract_context(selection)
    variables = context_to_variables(context)

    # note this only supports single workflow mutations at present
    workflow = variables['workflow'][0]
    try:
        client = get_client(workflow)
    except WorkflowStopped:
        raise Exception(
            f'Cannot peform command {mutation} on a stopped workflow'
        ) from None
    except (ClientError, ClientTimeout) as exc:
        raise Exception(
            f'Error connecting to workflow: {exc}'
        ) from None

    request_string = generate_mutation(mutation, variables)
    client(
        'graphql',
        {
            'request_string': request_string,
            'variables': variables
        }
    )


def offline_mutate(mutation, selection):
    """Issue a mutation over the CLI or other offline interface."""
    context = extract_context(selection)
    variables = context_to_variables(context, jobs=True)
    if 'job' in variables:
        for job in variables['job']:
            id_ = Tokens(job, relative=True).duplicate(
                workflow=variables['workflow'][0]
            )
            return OFFLINE_MUTATIONS['job'][mutation](id_.id)
    if 'task' in variables:
        for task in variables['task']:
            id_ = Tokens(task, relative=True).duplicate(
                workflow=variables['workflow'][0]
            )
            return OFFLINE_MUTATIONS['task'][mutation](id_.id)
    if 'workflow' in variables:
        for workflow in variables['workflow']:
            return OFFLINE_MUTATIONS['workflow'][mutation](workflow)
    else:
        return OFFLINE_MUTATIONS['user'][mutation]()
