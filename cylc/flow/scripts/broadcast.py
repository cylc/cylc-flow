#!/usr/bin/env python3

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

"""cylc broadcast [OPTIONS] ARGS

Override "[runtime]" configurations in a running workflow.

Uses for broadcast include making temporary changes to task behaviour, and
task-to-downstream-task communication via environment variables.

See also "cylc reload" which reads in the flow.cylc (or suite.rc) file.

A broadcast can set/override any "[runtime]" configuration for all cycles or
for a specific cycle. If a task is affected by specific-cycle and all-cycle
broadcasts at the same time, the specific takes precedence.

Broadcasts can also target all tasks, specific tasks or families of tasks. If a
task is affected by broadcasts to multiple ancestor namespaces (tasks it
inherits from), the result is determined by normal "[runtime]" inheritance.

Broadcasts are applied at the time of job submission.

Broadcasts persist, even across restarts. Broadcasts made to specific cycle
points will expire when the cycle point is older than the oldest active cycle
point in the workflow.

Active broadcasts can be revoked using the "clear" mode. Any broadcasts
matching the specified cycle points and namespaces will be revoked.

Note: a "clear" broadcast for a specific cycle or namespace does *not* clear
all-cycle or all-namespace broadcasts.

Examples:
  # To broadcast a variable to all tasks (quote items with internal spaces):
  $ cylc broadcast -s "[environment]VERSE = the quick brown fox" WORKFLOW

  # To do the same with a file:
  $ cat >'broadcast.cylc' <<'__FLOW__'
  > [environment]
  >     VERSE = the quick brown fox
  > __FLOW__
  $ cylc broadcast -F 'broadcast.cylc' WORKFLOW_ID

  # view active broadcasts
  $ cylc broadcast --display WORKFLOW_ID

  # To cancel the same broadcast:
  $ cylc broadcast --cancel "[environment]VERSE" WORKFLOW_ID

  # If -F FILE was used, the same file can be used to cancel the broadcast:
  $ cylc broadcast -G 'broadcast.cylc' WORKFLOW_ID

  # Use broadcast with multiple workflows
  $ cylc broadcast [options] WORKFLOW_ID_1// WORKFLOW_ID_2//

Use -d/--display to see active broadcasts. Multiple --cancel options or
multiple --set and --set-file options can be used on the same command line.
Multiple --set and --set-file options are cumulative.

The --set-file=FILE option can be used when broadcasting multiple values, or
when the value contains newline or other metacharacters. If FILE is "-", read
from standard input.

Broadcast cannot change [runtime] inheritance.
"""

from ansimarkup import parse as cparse
import asyncio
from copy import deepcopy
from functools import partial
import os.path
import re
import sys
from tempfile import NamedTemporaryFile
from typing import Any, Dict, TYPE_CHECKING

from cylc.flow.broadcast_report import (
    get_broadcast_bad_options_report,
    get_broadcast_change_report,
)
from cylc.flow.cfgspec.workflow import SPEC, upg
from cylc.flow.exceptions import InputError
from cylc.flow.network.client_factory import get_client
from cylc.flow.network.multi import call_multi_async
from cylc.flow.option_parsers import (
    WORKFLOW_ID_MULTI_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.parsec.config import ParsecConfig
from cylc.flow.parsec.util import listjoin
from cylc.flow.parsec.validate import cylc_config_validate
from cylc.flow.print_tree import get_tree
from cylc.flow.terminal import cli_function

if TYPE_CHECKING:
    from optparse import Values


REC_ITEM = re.compile(r'^\[([^\]]*)\](.*)$')

MUTATION = '''
mutation (
    $wFlows: [WorkflowID]!,
    $bMode: BroadcastMode!,
    $cPoints: [BroadcastCyclePoint],
    $nSpaces: [NamespaceName],
    $bSettings: [BroadcastSetting],
    $bCutoff: CyclePoint
) {
  broadcast (
    workflows: $wFlows,
    mode: $bMode,
    cyclePoints: $cPoints,
    namespaces: $nSpaces,
    settings: $bSettings,
    cutoff: $bCutoff
  ) {
    results {
      workflowId
      success
      message
    }
  }
}
'''

QUERY = '''
query (
  $wFlows: [ID],
  $nIds: [ID]
) {
  workflows (
    ids: $wFlows,
  ) {
    id
    broadcasts (ids: $nIds)
  }
}
'''


def get_padding(settings, level=0, padding=0):
    """Return the left padding for displaying a setting."""
    level += 1
    for key, val in settings.items():
        tmp = level * 2 + len(key)
        if tmp > padding:
            padding = tmp
        if isinstance(val, dict):
            padding = get_padding(val, level, padding)
    return padding


def get_rdict(left, right=None):
    """Check+transform left=right into a nested dict.

    left can be key, [key], [key1]key2, [key1][key2], [key1][key2]key3, etc.
    """
    if left == "inherit":
        raise InputError(
            "Inheritance cannot be changed by broadcast")
    rdict = {}
    cur_dict = rdict
    tail = left
    while tail:
        match = REC_ITEM.match(tail)
        if match:
            sect, tail = match.groups()
            if tail:
                # [sect]... = right
                cur_dict[sect.strip()] = {}
                cur_dict = cur_dict[sect.strip()]
            else:
                # [sect] = right
                cur_dict[sect.strip()] = right
        else:
            # item = right
            cur_dict[tail.strip()] = right
            tail = None
    upg({'runtime': {'__MANY__': rdict}}, 'test')
    # Perform validation, but don't coerce the original (deepcopy).
    cylc_config_validate(deepcopy(rdict), SPEC['runtime']['__MANY__'])
    return rdict


def files_to_settings(settings, setting_files, cancel_mode=False):
    """Parse setting files, and append to settings."""
    cfg = ParsecConfig(
        SPEC['runtime']['__MANY__'], validator=cylc_config_validate)
    for setting_file in setting_files:
        if setting_file == '-':
            with NamedTemporaryFile() as handle:
                handle.write(sys.stdin.read().encode())
                handle.seek(0, 0)
                cfg.loadcfg(handle.name)
        else:
            cfg.loadcfg(os.path.abspath(setting_file))
    stack = [([], cfg.get(sparse=True))]
    while stack:
        keys, item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                stack.append((keys + [key], value))
        else:
            settings.append({})
            cur_setting = settings[-1]
            while keys:
                key = keys.pop(0)
                if keys:
                    cur_setting[key] = {}
                    cur_setting = cur_setting[key]
                elif cancel_mode:
                    cur_setting[key] = None
                else:
                    if isinstance(item, list):
                        item = listjoin(item)
                    else:
                        item = str(item)
                    cur_setting[key] = item


def report_bad_options(bad_options, is_set=False):
    bad_opts = get_broadcast_bad_options_report(bad_options, is_set=is_set)
    if bad_opts is not None:
        return cparse(f'<red>{bad_opts}</red>')
    return bad_opts


def get_option_parser() -> COP:
    """CLI for "cylc broadcast"."""
    parser = COP(
        __doc__,
        comms=True,
        multiworkflow=True,
        argdoc=[WORKFLOW_ID_MULTI_ARG_DOC],
    )

    parser.add_option(
        "-p", "--point", metavar="CYCLE_POINT",
        help="Target cycle point. More than one can be added. "
             "Defaults to '*' with --set and --cancel, "
             "and nothing with --clear.",
        action="append", dest="point_strings", default=[])

    parser.add_option(
        "-n", "--namespace", metavar="NAME",
        help="Target namespace. Defaults to 'root' with "
             "--set and --cancel, and nothing with --clear.",
        action="append", dest="namespaces", default=[])

    parser.add_option(
        "-s", "--set", metavar="[SEC]ITEM=VALUE",
        help="A [runtime] config item and value to broadcast.",
        action="append", dest="settings", default=[])

    parser.add_option(
        "-F", "--set-file", "--file", metavar="FILE",
        help="File with config to broadcast. Can be used multiple times.",
        action="append", dest="setting_files", default=[])

    parser.add_option(
        "-c", "--cancel", metavar="[SEC]ITEM",
        help="An item-specific broadcast to cancel.",
        action="append", dest="cancel", default=[])

    parser.add_option(
        "-G", "--cancel-file", metavar="FILE",
        help="File with broadcasts to cancel. Can be used multiple times.",
        action="append", dest="cancel_files", default=[])

    parser.add_option(
        "-C", "--clear",
        help="Cancel all broadcasts, or with -p/--point, "
             "-n/--namespace, cancel all broadcasts to targeted "
             "namespaces and/or cycle points. Use \"-C -p '*'\" "
             "to cancel all all-cycle broadcasts without canceling "
             "all specific-cycle broadcasts.",
        action="store_true", dest="clear", default=False)

    parser.add_option(
        "-e", "--expire", metavar="CYCLE_POINT",
        help="Cancel any broadcasts that target cycle "
             "points earlier than, but not inclusive of, CYCLE_POINT.",
        action="store", default=None, dest="expire")

    parser.add_option(
        "-d", "--display",
        help="Display active broadcasts.",
        action="store_true", default=False, dest="show")

    parser.add_option(
        "-k", "--display-task", metavar="TASK_ID_GLOB",
        help=(
            "Print active broadcasts for a given task "
            "(in the format cycle/task)."
        ),
        action="store", default=None, dest="showtask")

    parser.add_option(
        "-b", "--box",
        help="Use unicode box characters with -d, -k.",
        action="store_true", default=False, dest="unicode")

    parser.add_option(
        "-r", "--raw",
        help="With -d/--display or -k/--display-task, write out "
             "the broadcast config structure in raw Python form.",
        action="store_true", default=False, dest="raw")

    return parser


async def run(options: 'Values', workflow_id):
    """Implement cylc broadcast."""
    pclient = get_client(workflow_id, timeout=options.comms_timeout)

    ret: Dict[str, Any] = {
        'stdout': [],
        'stderr': [],
        'exit': 0,
    }

    mutation_kwargs: Dict[str, Any] = {
        'request_string': MUTATION,
        'variables': {
            'wFlows': [workflow_id],
            'bMode': 'Set',
            'cPoints': options.point_strings,
            'nSpaces': options.namespaces,
            'bSettings': options.settings,
            'bCutoff': options.expire,
        }
    }

    query_kwargs: Dict[str, Any] = {
        'request_string': QUERY,
        'variables': {
            'wFlows': [workflow_id],
            'nIds': []
        }

    }

    if options.show or options.showtask:
        if options.showtask:
            try:
                query_kwargs['variables']['nIds'] = [options.showtask]
            except ValueError:
                # TODO validate showtask?
                raise InputError(
                    'TASK_ID_GLOB must be in the format: cycle/task'
                )
        result = await pclient.async_request('graphql', query_kwargs)
        for wflow in result['workflows']:
            settings = wflow['broadcasts']
            padding = get_padding(settings) * ' '
            if options.raw:
                ret['stdout'].append(str(settings))
            else:
                ret['stdout'].extend(
                    get_tree(settings, padding, options.unicode)
                )
        return ret

    report_cancel = True
    report_set = False
    if options.clear:
        mutation_kwargs['variables']['bMode'] = 'Clear'

    if options.expire:
        mutation_kwargs['variables']['bMode'] = 'Expire'

    # implement namespace and cycle point defaults here
    namespaces = options.namespaces
    if not namespaces:
        namespaces = ["root"]
    point_strings = options.point_strings
    if not point_strings:
        point_strings = ["*"]

    if options.cancel or options.cancel_files:
        settings = []
        for option_item in options.cancel:
            if "=" in option_item:
                raise InputError(
                    "--cancel=[SEC]ITEM does not take a value")
            option_item = option_item.strip()
            setting = get_rdict(option_item)
            settings.append(setting)
        files_to_settings(settings, options.cancel_files, options.cancel)
        mutation_kwargs['variables'].update(
            {
                'bMode': 'Clear',
                'cPoints': point_strings,
                'nSpaces': namespaces,
                'bSettings': settings,
            }
        )

    if options.settings or options.setting_files:
        settings = []
        for option_item in options.settings:
            if "=" not in option_item:
                raise InputError(
                    "--set=[SEC]ITEM=VALUE requires a value")
            lhs, rhs = [s.strip() for s in option_item.split("=", 1)]
            setting = get_rdict(lhs, rhs)
            settings.append(setting)
        files_to_settings(settings, options.setting_files)
        mutation_kwargs['variables'].update(
            {
                'bMode': 'Set',
                'cPoints': point_strings,
                'nSpaces': namespaces,
                'bSettings': settings,
            }
        )
        report_cancel = False
        report_set = True

    results = await pclient.async_request('graphql', mutation_kwargs)
    try:
        for result in results['data']['broadcast']['results']:
            modified_settings = result['message'][0]
            bad_options = result['message'][1]
            if modified_settings:
                ret['stdout'].append(
                    get_broadcast_change_report(
                        modified_settings,
                        is_cancel=report_cancel,
                    )
                )
        bad_result = report_bad_options(bad_options, is_set=report_set)
    except TypeError:
        # Catch internal API server errors
        bad_result = cparse(f'<red>{results}</red>')

    if bad_result:
        ret['stderr'].append(f'ERROR: {bad_result}')
        ret['exit'] = 1
    return ret


def report(response):
    return (
        '\n'.join(response['stdout']),
        '\n'.join(line for line in response['stderr'] if line is not None),
        response['exit'] == 0,
    )


@cli_function(get_option_parser)
def main(_, options: 'Values', *ids) -> None:
    rets = asyncio.run(_main(options, *ids))
    sys.exit(all(rets.values()) is False)


async def _main(options: 'Values', *ids):
    return await call_multi_async(
        partial(run, options),
        *ids,
        constraint='workflows',
        report=report,
    )
