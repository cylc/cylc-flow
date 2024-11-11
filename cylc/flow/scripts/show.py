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

"""cylc show [OPTIONS] ARGS

Display workflow and task information, for tasks in the current n-window.

Query a running workflow for:
  # view workflow metadata
  $ cylc show my_workflow

  # view task metadata
  $ cylc show my_workflow --task-def my_task

  # view prerequisites & outputs for a live task
  $ cylc show my_workflow//1/my_task

Output completion status is shown for all tasks in the current n-window.

Prerequisite satisfaction is not shown for past tasks reloaded from the
workflow database.
"""

import asyncio
import re
import json
import sys
from textwrap import indent
from typing import Any, Dict, TYPE_CHECKING

from ansimarkup import ansiprint

from metomi.isodatetime.data import (
    get_timepoint_from_seconds_since_unix_epoch as seconds2point)

from cylc.flow.exceptions import InputError
from cylc.flow.id import Tokens
from cylc.flow.id_cli import parse_ids
from cylc.flow.network.client_factory import get_client
from cylc.flow.task_outputs import TaskOutputs
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_RUNNING
)
from cylc.flow.option_parsers import (
    CylcOptionParser as COP,
    ID_MULTI_ARG_DOC,
    Options,
)
from cylc.flow.terminal import cli_function
from cylc.flow.util import BOOL_SYMBOLS


if TYPE_CHECKING:
    from optparse import Values


WORKFLOW_META_QUERY = '''
query ($wFlows: [ID]!) {
  workflows (ids: $wFlows, stripNull: false) {
    meta {
      title
      description
      URL
      userDefined
    }
  }
}
'''

TASK_META_QUERY = '''
query ($wFlows: [ID]!, $taskIds: [ID]) {
  tasks (workflows: $wFlows, ids: $taskIds, stripNull: false) {
    name
    meta {
      title
      description
      URL
      userDefined
    }
  }
}
'''

TASK_PREREQS_QUERY = '''
query ($wFlows: [ID]!, $taskIds: [ID]) {
  taskProxies (workflows: $wFlows, ids: $taskIds, stripNull: false) {
    id
    name
    cyclePoint
    state
    task {
      meta {
        title
        description
        URL
        userDefined
      }
    }
    prerequisites {
      expression
      conditions {
        exprAlias
        taskId
        reqState
        message
        satisfied
      }
      satisfied
    }
    outputs {
      label
      message
      satisfied
    }
    externalTriggers {
      id
      label
      message
      satisfied
    }
    xtriggers {
      id
      label
      satisfied
    }
    runtime {
      completion
    }
  }
}
'''


SATISFIED = BOOL_SYMBOLS[True]
UNSATISFIED = BOOL_SYMBOLS[False]


def print_msg_state(msg, state):
    if state:
        ansiprint(f'<green>  {SATISFIED} {msg}</green>')
    else:
        ansiprint(f'<red>  {UNSATISFIED} {msg}</red>')


def print_completion_state(t_proxy):
    # create task outputs object
    outputs = TaskOutputs(t_proxy["runtime"]["completion"])

    for output in t_proxy['outputs']:
        outputs.add(output['label'], output['message'])
        if output['satisfied']:
            outputs.set_message_complete(output['message'])

    ansiprint(
        f'<bold>output completion:</bold>'
        f' {"complete" if outputs.is_complete() else "incomplete"}'
        f'\n{indent(outputs.format_completion_status(ansimarkup=2), "  ")}'
    )


def flatten_data(data, flat_data=None):
    """Reduce a nested data structure to a flat one.

    Examples:
        It flattens out nested dictionaries:
        >>> flatten_data({})
        {}
        >>> flatten_data({'a': 1})
        {'a': 1}
        >>> flatten_data({'a': {'b': 2, 'c': {'d': 4}}})
        {'b': 2, 'd': 4}

        It iterates through any lists that it finds:
        >>> flatten_data({'a': [{'b': 2}, {'c': 3}]})
        {'b': 2, 'c': 3}

        Overriding is determined by iteration order (don't rely on it):
        >>> flatten_data({'a': 1, 'b': {'a': 2}})
        {'a': 2}

        It can't flatten things which aren't dicts:
        >>> flatten_data({'a': ['x', 'y']})
        Traceback (most recent call last):
        AttributeError: 'str' object has no attribute 'items'

    """
    if flat_data is None:
        flat_data = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flatten_data(value, flat_data)
        elif isinstance(value, list):
            for member in value:
                flatten_data(member, flat_data)
        else:
            flat_data[key] = value
    return flat_data


def get_option_parser():
    parser = COP(
        __doc__,
        comms=True,
        multitask=True,
        argdoc=[ID_MULTI_ARG_DOC],
    )

    parser.add_option(
        '--list-prereqs',
        action="store_true",
        default=False,
        help="Print a task's pre-requisites as a list.",
    )

    parser.add_option(
        '--json',
        action="store_true",
        default=False,
        help="Print output in JSON format.",
    )

    parser.add_option(
        '--task-def',
        action="append",
        default=None,
        dest='task_defs',
        metavar='TASK_NAME',
        help="View metadata for a task definition (can be used multiple times)"
    )

    return parser


ShowOptions = Options(get_option_parser())


async def workflow_meta_query(workflow_id, pclient, options, json_filter):
    query = WORKFLOW_META_QUERY
    query_kwargs = {
        'request_string': query,
        'variables': {'wFlows': [workflow_id]}
    }
    # Print workflow info.
    results = await pclient.async_request('graphql', query_kwargs)
    for workflow_id in results['workflows']:
        flat_data = flatten_data(workflow_id)
        if options.json:
            json_filter.update(flat_data)
        else:
            for key, value in sorted(flat_data.items(), reverse=True):
                ansiprint(
                    f'<bold>{key}:</bold> {value or "<m>(not given)</m>"}'
                )
    return 0


async def prereqs_and_outputs_query(
    workflow_id,
    tokens_list,
    pclient,
    options,
    json_filter,
):
    ids_list = [
        # convert the tokens into standardised IDs
        tokens.relative_id_with_selectors
        for tokens in tokens_list
    ]

    tp_query = TASK_PREREQS_QUERY
    tp_kwargs = {
        'request_string': tp_query,
        'variables': {
            'wFlows': [workflow_id],
            'taskIds': ids_list,
        }
    }
    results = await pclient.async_request('graphql', tp_kwargs)
    task_proxies = sorted(results['taskProxies'],
                          key=lambda proxy: proxy['id'])
    multi = len(task_proxies) > 1
    for t_proxy in task_proxies:
        task_id = Tokens(t_proxy['id']).relative_id
        state = t_proxy['state']
        if options.json:
            json_filter.update({task_id: t_proxy})
        else:
            if multi:
                ansiprint(f'\n<bold>Task ID:</bold> {task_id}')
            prereqs = []
            for item in t_proxy['prerequisites']:
                prefix = ''
                multi_cond = len(item['conditions']) > 1
                if multi_cond:
                    prereqs.append([
                        True,
                        '',
                        item['expression'].replace('c', ''),
                        item['satisfied']
                    ])
                for cond in item['conditions']:
                    if multi_cond and not options.list_prereqs:
                        prefix = f'\t{cond["exprAlias"].strip("c")} = '
                    prereqs.append([
                        False,
                        prefix,
                        f'{cond["taskId"]} {cond["reqState"]}',
                        cond['satisfied']
                    ])
            if options.list_prereqs:
                for composite, _, msg, _ in prereqs:
                    if not composite:
                        print(msg)
            else:
                flat_meta = flatten_data(t_proxy['task']['meta'])
                for key, value in sorted(flat_meta.items(), reverse=True):
                    ansiprint(
                        f'<bold>{key}:</bold>'
                        f' {value or "<m>(not given)</m>"}')

                ansiprint(f'<bold>state:</bold> {state}')

                # prerequisites
                pre_txt = "<bold>prerequisites:</bold>"
                if not prereqs:
                    ansiprint(f"{pre_txt} (None)")
                elif (
                    TASK_STATUSES_ORDERED.index(state) >
                    TASK_STATUSES_ORDERED.index(TASK_STATUS_RUNNING)
                ):
                    # We only store prerequisites in the DB for n>0.
                    ansiprint(f"{pre_txt} (n/a for past tasks)")
                else:
                    ansiprint(
                        f"{pre_txt}"
                        f" ('<red>{UNSATISFIED}</red>': not satisfied)"
                    )
                    for _, prefix, msg, state in prereqs:
                        print_msg_state(f'{prefix}{msg}', state)

                # outputs
                ansiprint(
                    '<bold>outputs:</bold>'
                    f" ('<red>{UNSATISFIED}</red>': not completed)")
                if not t_proxy['outputs']:  # (Not possible - standard outputs)
                    print('  (None)')
                for output in t_proxy['outputs']:
                    info = f'{task_id} {output["label"]}'
                    print_msg_state(info, output['satisfied'])
                if (
                        t_proxy['externalTriggers']
                        or t_proxy['xtriggers']
                ):
                    ansiprint(
                        "<bold>other:</bold>"
                        f" ('<red>{UNSATISFIED}</red>': not satisfied)"
                    )
                    for ext_trig in t_proxy['externalTriggers']:
                        state = ext_trig['satisfied']
                        print_msg_state(
                            f'{ext_trig["label"]} ... {state}',
                            state)
                    for xtrig in t_proxy['xtriggers']:
                        label = get_wallclock_label(xtrig) or xtrig['id']
                        state = xtrig['satisfied']
                        print_msg_state(
                            f'xtrigger "{xtrig["label"]} = {label}"',
                            state)

                print_completion_state(t_proxy)

    if not task_proxies:
        ansiprint(
            "<red>No matching active tasks found: "
            f"{', '.join(ids_list)}</red>",
            file=sys.stderr,
        )
        return 1
    return 0


def get_wallclock_label(xtrig: Dict[str, Any]) -> str:
    """Return a label for an xtrigger if it is a wall_clock trigger.

    Returns:
        A label or False.

    Examples:
        >>> this = get_wallclock_label

        >>> this({'id': 'wall_clock(trigger_time=0)'})
        'wall_clock(trigger_time=1970-01-01T00:00:00Z)'

        >>> this({'id': 'wall_clock(trigger_time=440143843)'})
        'wall_clock(trigger_time=1983-12-13T06:10:43Z)'

    """
    wallclock_trigger = re.findall(
        r'wall_clock\(trigger_time=(.*)\)', xtrig['id'])
    if wallclock_trigger:
        return (
            'wall_clock(trigger_time='
            f'{str(seconds2point(wallclock_trigger[0], True))})'
        )
    return ''


async def task_meta_query(
    workflow_id,
    task_names,
    pclient,
    options,
    json_filter,
):
    tasks_query = TASK_META_QUERY
    tasks_kwargs = {
        'request_string': tasks_query,
        'variables': {
            'wFlows': [workflow_id],
            'taskIds': task_names,
        },
    }
    # Print workflow info.
    results = await pclient.async_request('graphql', tasks_kwargs)
    multi = len(results['tasks']) > 1
    for task in results['tasks']:
        flat_data = flatten_data(task['meta'])
        if options.json:
            json_filter.update({task['name']: flat_data})
        else:
            if multi:
                print(f'\nTASK NAME: {task["name"]}')
            for key, value in sorted(flat_data.items(), reverse=True):
                ansiprint(
                    f'<bold>{key}:</bold> {value or "<m>(not given)</m>"}')
    return 0


async def show(workflow_id, tokens_list, opts):
    pclient = get_client(
        workflow_id,
        timeout=opts.comms_timeout,
    )
    json_filter: 'Dict' = {}

    ret = 0
    if opts.task_defs:
        ret = await task_meta_query(
            workflow_id,
            opts.task_defs,
            pclient,
            opts,
            json_filter,
        )
    elif not tokens_list:
        ret = await workflow_meta_query(
            workflow_id,
            pclient,
            opts,
            json_filter,
        )
    else:
        ret = await prereqs_and_outputs_query(
            workflow_id,
            tokens_list,
            pclient,
            opts,
            json_filter,
        )

    if opts.json:
        print(json.dumps(json_filter, indent=4))

    return ret


@cli_function(get_option_parser)
def main(_, options: 'Values', *ids) -> None:
    """Implement "cylc show" CLI."""
    workflow_args, _ = parse_ids(
        *ids,
        constraint='mixed',
        max_workflows=1,
    )
    workflow_id = next(iter(workflow_args))
    tokens_list = workflow_args[workflow_id]

    if tokens_list and options.task_defs:
        raise InputError(
            'Cannot query both live tasks and task definitions.'
        )

    ret = asyncio.run(show(workflow_id, tokens_list, options))
    sys.exit(ret)
