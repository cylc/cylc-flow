#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Common utilities for Tui."""

from time import time

from cylc.flow.data_store_mgr import ID_DELIM
from cylc.flow.task_state import (
    TASK_STATUS_RUNNING
)
from cylc.flow.tui import (
    JOB_COLOURS,
    JOB_ICON,
    TASK_ICONS,
    TASK_MODIFIERS
)
from cylc.flow.wallclock import get_unix_time_from_time_string


def get_task_icon(status, is_held, start_time=None, mean_time=None):
    """Return a Unicode string to represent a task.

    Arguments:
        status (str):
            A Cylc task status string.
        is_held (bool):
            True if the task is in a held state.
        start_time (str):
            Start date time string.
        mean_time (int):
            Execution mean time.

    Returns:
        list - Text content for the urwid.Text widget,
        may be a string, tuple or list, see urwid docs.

    """
    ret = []
    if is_held:
        ret.append(TASK_MODIFIERS['held'])
    if (
            status == TASK_STATUS_RUNNING
            and start_time
            and mean_time
    ):
        start_time = get_unix_time_from_time_string(start_time)
        progress = (time() - start_time) / mean_time
        if progress >= 0.75:
            status = f'{TASK_STATUS_RUNNING}:75'
        elif progress >= 0.5:
            status = f'{TASK_STATUS_RUNNING}:50'
        elif progress >= 0.25:
            status = f'{TASK_STATUS_RUNNING}:25'
        else:
            status = f'{TASK_STATUS_RUNNING}:0'
    ret.append(TASK_ICONS[status])
    return ret


def idpop(id_):
    """Remove the last element of a node id.

    Example:
        >>> id_ = ID_DELIM.join(['a', 'b', 'c'])
        >>> idpop(id_).split(ID_DELIM)
        ['a', 'b']

    """
    return id_.rsplit(ID_DELIM, 1)[0]


def compute_tree(flow):
    """Digest GraphQL data to produce a tree.

    Arguments:
        flow (dict):
            A dictionary representing a single workflow.

    Returns:
        dict - A top-level workflow node.

    """
    nodes = {}
    flow_node = add_node(
        'workflow', flow['id'], nodes, data=flow)

    # populate cycle nodes
    for cycle in flow['cyclePoints']:
        cycle['id'] = idpop(cycle['id'])  # strip the family off of the id
        cycle_node = add_node('cycle', cycle['id'], nodes, data=cycle)
        flow_node['children'].append(cycle_node)

    # populate family nodes
    for family in flow['familyProxies']:
        add_node('family', family['id'], nodes, data=family)

    # create cycle/family tree
    for family in flow['familyProxies']:
        family_node = add_node(
            'family', family['id'], nodes)
        first_parent = family['firstParent']
        if (
                first_parent
                and first_parent['name'] != 'root'
        ):
            parent_node = add_node(
                'family', first_parent['id'], nodes)
            parent_node['children'].append(family_node)
        else:
            add_node(
                'cycle', idpop(family['id']), nodes
            )['children'].append(family_node)

    # add leaves
    for task in flow['taskProxies']:
        parents = task['parents']
        if not parents:
            # handle inherit none by defaulting to root
            parents = [{'name': 'root'}]
        task_node = add_node(
            'task', task['id'], nodes, data=task)
        if parents[0]['name'] == 'root':
            family_node = add_node(
                'cycle', idpop(task['id']), nodes)
        else:
            family_node = add_node(
                'family', parents[0]['id'], nodes)
        family_node['children'].append(task_node)
        for job in task['jobs']:
            job_node = add_node(
                'job', job['id'], nodes, data=job)
            job_info_node = add_node(
                'job_info', job['id'] + '_info', nodes, data=job)
            job_node['children'] = [job_info_node]
            task_node['children'].append(job_node)

    # sort
    for (type_, _), node in nodes.items():
        if type_ != 'task':
            node['children'].sort(
                key=lambda x: x['id_']
            )

    return flow_node


def dummy_flow():
    """Return a blank workflow node."""
    return add_node(
        'worflow',
        '',
        {},
        {
            'id': 'Loading...'
        }
    )


def dummy_flow(data):
    return add_node(
        'workflow',
        '',
        {},
        data
    )


def add_node(type_, id_, nodes, data=None):
    """Create a node add it to the store and return it.

    Arguments:
        type_ (str):
            A string to represent the node type.
        id_ (str):
            A unique identifier for this node.
        nodes (dict):
            The node store to add the new node to.
        data (dict):
            An optional dictionary of data to add to this node.
            Can be left to None if retrieving a node from the store.

    Returns:
        dict - The requested node.

    """
    if (type_, id_) not in nodes:
        nodes[(type_, id_)] = {
            'children': [],
            'id_': id_,
            'data': data or {},
            'type_': type_
        }
    return nodes[(type_, id_)]


def get_job_icon(status):
    """Return a unicode string to represent a job.

    Arguments:
        status (str): A Cylc job status string.

    Returns:
        list - Text content for the urwid.Text widget,
        may be a string, tuple or list, see urwid docs.

    """
    return [
        (f'job_{status}', JOB_ICON)
    ]


def get_task_status_summary(flow):
    """Return a task status summary line for this workflow.

    Arguments:
        flow (dict):
            GraphQL JSON response for this workflow.

    Returns:
        list - Text list for the urwid.Text widget.

    """
    state_totals = flow['stateTotals']
    return [
        [
            ('', ' '),
            (f'job_{state}', str(state_totals[state])),
            (f'job_{state}', JOB_ICON)
        ]
        for state, colour in JOB_COLOURS.items()
        if state in state_totals
        if state_totals[state]
    ]


def get_workflow_status_str(flow):
    """Return a suite status string for the header.

    Arguments:
        flow (dict):
            GraphQL JSON response for this workflow.

    Returns:
        list - Text list for the urwid.Text widget.

    """
    status = flow['status']
    return [
        (
            'title',
            flow['name'],
        ),
        ' - ',
        (
            f'suite_{status}',
            status
        )
    ]


def render_node(node, data, type_):
    """Render a tree node as text.

    Args:
        node (MonitorNode):
            The node to render.
        data (dict):
            Data associated with that node.
        type_ (str):
            The node type (e.g. `task`, `job`, `family`).

    """
    if type_ == 'job_info':
        key_len = max(len(key) for key in data)
        ret = [
            f'{key} {" " * (key_len - len(key))} {value}\n'
            for key, value in data.items()
        ]
        ret[-1] = ret[-1][:-1]  # strip trailing newline
        return ret

    if type_ == 'job':
        return [
            f'#{data["submitNum"]:02d} ',
            get_job_icon(data['state'])
        ]

    if type_ == 'task':
        start_time = None
        mean_time = None
        try:
            # due to sorting this is the most recent job
            first_child = node.get_child_node(0)
        except IndexError:
            first_child = None

        # progress information
        if data['state'] == TASK_STATUS_RUNNING:
            start_time = first_child.get_value()['data']['startedTime']
            mean_time = data['task']['meanElapsedTime']

        # the task icon
        ret = get_task_icon(
            data['state'],
            data['isHeld'],
            start_time=start_time,
            mean_time=mean_time
        )

        # the most recent job status
        ret.append(' ')
        if first_child:
            state = first_child.get_value()['data']['state']
            ret += [(f'job_{state}', f'{JOB_ICON}'), ' ']

        # the task name
        ret.append(f'{data["name"]}')
        return ret

    if type_ in ['family', 'cycle']:
        return [
            get_task_icon(
                data['state'],
                data['isHeld']
            ),
            ' ',
            data['id'].rsplit(ID_DELIM, 1)[-1]
        ]

    return data['id'].rsplit(ID_DELIM, 1)[-1]


PARTS = [
    'user',
    'workflow',
    'cycle_point',
    'task',
    'job'
]


def extract_context(selection):
    """Return a dictionary of all component types in the selection.

    Args:
        selection (list):
            List of element id's as extracted from the data store / graphql.

    Examples:
        >>> extract_context(['a|b', 'a|c'])
        {'user': ['a'], 'workflow': ['b', 'c']}

        >>> extract_context(['a|b|c|d|e']
        ... )  # doctest: +NORMALIZE_WHITESPACE
        {'user': ['a'], 'workflow': ['b'], 'cycle_point': ['c'],
        'task': ['d'], 'job': ['e']}

    """
    context = {type_: set() for type_ in PARTS}
    for item in selection:
        parts = item.split(ID_DELIM)
        for type_, part in zip(PARTS, parts):
            context[type_].add(part)
    return {
        key: list(sorted(value))
        for key, value in context.items()
        if value
    }
