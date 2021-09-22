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

Display workflow and task information.

Query a running workflow for:
  $ cylc show REG  # workflow metadata
  $ cylc show REG TASK_NAME  # task metadata
  $ cylc show REG TASK_GLOB  # prerequisites and outputs of task instances

Prerequisite and output status is indicated for current active tasks.
"""

import json
from optparse import Values
import sys

from ansimarkup import ansiprint

from cylc.flow import ID_DELIM
from cylc.flow.network.client_factory import get_client
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_id import TaskID
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import parse_reg


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
    name
    cyclePoint
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
    clockTrigger {
      timeString
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
  }
}
'''


def print_msg_state(msg, state):
    if state:
        ansiprint(f'<green>  + {msg}</green>')
    else:
        ansiprint(f'<red>  - {msg}</red>')


def flatten_data(data, flat_data=None):
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
        __doc__, comms=True, multitask=True,
        argdoc=[
            ('REG', 'Workflow name'),
            ('[TASK_NAME or TASK_GLOB ...]', 'Task names or match patterns')])

    parser.add_option('--list-prereqs', action="store_true", default=False,
                      help="Print a task's pre-requisites as a list.")

    parser.add_option('--json', action="store_true", default=False,
                      help="Print output in JSON format.")

    return parser


@cli_function(get_option_parser)
def main(_, options: 'Values', reg: str, *task_args: str) -> None:
    """Implement "cylc show" CLI."""
    reg, _ = parse_reg(reg)
    pclient = get_client(reg, timeout=options.comms_timeout)
    json_filter = {}

    if not task_args:
        query = WORKFLOW_META_QUERY
        query_kwargs = {
            'request_string': query,
            'variables': {'wFlows': [reg]}
        }
        # Print workflow info.
        results = pclient('graphql', query_kwargs)
        for reg in results['workflows']:
            flat_data = flatten_data(reg)
            if options.json:
                json_filter.update(flat_data)
            else:
                for key, value in sorted(flat_data.items(), reverse=True):
                    ansiprint(
                        f'<bold>{key}:</bold> {value or "<m>(not given)</m>"}')

    task_names = [arg for arg in task_args if TaskID.is_valid_name(arg)]
    task_ids = [arg for arg in task_args if TaskID.is_valid_id_2(arg)]

    if task_names:
        tasks_query = TASK_META_QUERY
        tasks_kwargs = {
            'request_string': tasks_query,
            'variables': {'wFlows': [reg], 'taskIds': task_names}
        }
        # Print workflow info.
        results = pclient('graphql', tasks_kwargs)
        multi = len(results['tasks']) > 1
        for task in results['tasks']:
            flat_data = flatten_data(task['meta'])
            if options.json:
                json_filter.update({task['name']: flat_data})
            else:
                if multi:
                    print(f'----\nTASK NAME: {task["name"]}')
                for key, value in sorted(flat_data.items(), reverse=True):
                    ansiprint(
                        f'<bold>{key}:</bold> {value or "<m>(not given)</m>"}')

    if task_ids:
        tp_query = TASK_PREREQS_QUERY
        tp_kwargs = {
            'request_string': tp_query,
            'variables': {
                'wFlows': [reg],
                'taskIds': [
                    f'{c}{ID_DELIM}{n}'
                    for n, c in [
                        TaskID.split(t_id)
                        for t_id in task_ids
                        if TaskID.is_valid_id(t_id)
                    ]
                ] + [
                    f'{c}{ID_DELIM}{n}'
                    for c, n in [
                        t_id.rsplit(TaskID.DELIM2, 1)
                        for t_id in task_ids
                        if not TaskID.is_valid_id(t_id)
                    ]
                ]
            }
        }
        results = pclient('graphql', tp_kwargs)
        multi = len(results['taskProxies']) > 1
        for t_proxy in results['taskProxies']:
            task_id = TaskID.get(t_proxy['name'], t_proxy['cyclePoint'])
            if options.json:
                json_filter.update({task_id: t_proxy})
            else:
                if multi:
                    print(f'----\nTASK ID: {task_id}')
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
                        _, _, point, name = cond['taskId'].split(ID_DELIM)
                        cond_id = TaskID.get(name, point)
                        prereqs.append([
                            False,
                            prefix,
                            f'{cond_id} {cond["reqState"]}',
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
                    ansiprint(
                        '\n<bold>prerequisites</bold>'
                        ' (<red>- => not satisfied</red>):')
                    if not prereqs:
                        print('  (None)')
                    for _, prefix, msg, state in prereqs:
                        print_msg_state(f'{prefix}{msg}', state)

                    ansiprint(
                        '\n<bold>outputs</bold>'
                        ' (<red>- => not completed</red>):')
                    if not t_proxy['outputs']:
                        print('  (None)')
                    for output in t_proxy['outputs']:
                        info = f'{task_id} {output["label"]}'
                        print_msg_state(info, output['satisfied'])
                    if (
                            t_proxy['clockTrigger']['timeString']
                            or t_proxy['externalTriggers']
                            or t_proxy['xtriggers']
                    ):
                        ansiprint(
                            '\n<bold>other</bold>'
                            ' (<red>- => not satisfied</red>):')
                        if t_proxy['clockTrigger']['timeString']:
                            state = t_proxy['clockTrigger']['satisfied']
                            time_str = t_proxy['clockTrigger']['timeString']
                            print_msg_state(
                                'Clock trigger time reached',
                                state)
                            print(f'  o Triggers at ... {time_str}')
                        for ext_trig in t_proxy['externalTriggers']:
                            state = ext_trig['satisfied']
                            print_msg_state(
                                f'{ext_trig["label"]} ... {state}',
                                state)
                        for xtrig in t_proxy['xtriggers']:
                            state = xtrig['satisfied']
                            print_msg_state(
                                f'xtrigger "{xtrig["label"]} = {xtrig["id"]}"',
                                state)
        if not results['taskProxies']:
            ansiprint(
                f"<red>No matching tasks found: {task_ids}",
                file=sys.stderr)
            sys.exit(1)

    if options.json:
        print(json.dumps(json_filter, indent=4))


if __name__ == "__main__":
    main()
