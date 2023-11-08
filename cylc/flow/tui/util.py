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
"""Common utilities for Tui."""

from contextlib import contextmanager
from getpass import getuser
from itertools import zip_longest
import re
from time import time
from typing import Tuple

from cylc.flow import LOG
from cylc.flow.id import Tokens
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


# the Tui user, note this is always the same as the workflow owner
# (Tui doesn't do multi-user stuff)
ME = getuser()


@contextmanager
def suppress_logging():
    """Suppress Cylc logging.

    Log goes to stdout/err which can pollute Urwid apps.
    Patching sys.stdout/err is insufficient so we set the level to something
    silly for the duration of this context manager then set it back again
    afterwards.
    """
    level = LOG.getEffectiveLevel()
    LOG.setLevel(99999)
    yield
    LOG.setLevel(level)


def get_task_icon(
    status,
    *,
    is_held=False,
    is_queued=False,
    is_runahead=False,
    start_time=None,
    mean_time=None
):
    """Return a Unicode string to represent a task.

    Arguments:
        status (str):
            A Cylc task status string.
        is_held (bool):
            True if the task is held.
        is_queued (bool):
            True if the task is queued.
        is_runahead (bool):
            True if the task is runahead limited.
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
    elif is_runahead:
        ret.append(TASK_MODIFIERS['runahead'])
    elif is_queued:
        ret.append(TASK_MODIFIERS['queued'])
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

    Examples:
        >>> idpop('w//c/t/j')
        'w//c/t'
        >>> idpop('c/t/j')
        '//c/t'
        >>> idpop('c/t')
        '//c'
        >>> idpop('c')
        Traceback (most recent call last):
        ValueError: No tokens provided
        >>> idpop('')
        Traceback (most recent call last):
        ValueError: Invalid Cylc identifier: //

    """
    relative = '//' not in id_
    tokens = Tokens(id_, relative=relative)
    tokens.pop_token()
    return tokens.id


def compute_tree(data):
    """Digest GraphQL data to produce a tree."""
    root_node = add_node('root', 'root', {}, data={})

    for flow in data['workflows']:
        nodes = {}
        flow_node = add_node(
            'workflow', flow['id'], nodes, data=flow)
        root_node['children'].append(flow_node)

        # populate cycle nodes
        for cycle in flow.get('cyclePoints', []):
            cycle['id'] = idpop(cycle['id'])  # strip the family off of the id
            cycle_node = add_node('cycle', cycle['id'], nodes, data=cycle)
            flow_node['children'].append(cycle_node)

        # populate family nodes
        for family in flow.get('familyProxies', []):
            add_node('family', family['id'], nodes, data=family)

        # create cycle/family tree
        for family in flow.get('familyProxies', []):
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
        for task in flow.get('taskProxies', []):
            # If there's no first parent, the child will have been deleted
            # during/after API query resolution. So ignore.
            if not task['firstParent']:
                continue
            task_node = add_node(
                'task', task['id'], nodes, data=task)
            if task['firstParent']['name'] == 'root':
                family_node = add_node(
                    'cycle', idpop(task['id']), nodes)
            else:
                family_node = add_node(
                    'family', task['firstParent']['id'], nodes)
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
                # NOTE: jobs are sorted by submit-num in the GraphQL query
                node['children'].sort(
                    key=lambda x: NaturalSort(x['id_'])
                )

        # spring nodes
        if 'port' not in flow:
            # the "port" field is only available via GraphQL
            # so we are not connected to this workflow yet
            flow_node['children'].append(
                add_node(
                    '#spring',
                    '#spring',
                    nodes,
                    data={
                        'id': flow.get('_tui_data', 'Loading ...'),
                    }
                )
            )

    return root_node


class NaturalSort:
    """An object to use as a sort key for sorting strings as a human would.

    This recognises numerical patterns within strings.

    Examples:
        >>> N = NaturalSort

        String comparisons work as normal:
        >>> N('') < N('')
        False
        >>> N('a') < N('b')
        True
        >>> N('b') < N('a')
        False

        Integer comparisons work as normal:
        >>> N('9') < N('10')
        True
        >>> N('10') < N('9')
        False

        Integers rank higher than strings:
        >>> N('1') < N('a')
        True
        >>> N('a') < N('1')
        False

        Integers within strings are sorted numerically:
        >>> N('a9b') < N('a10b')
        True
        >>> N('a10b') < N('a9b')
        False

        Lexicographical rules apply when substrings match:
        >>> N('a1b2') < N('a1b2c3')
        True
        >>> N('a1b2c3') < N('a1b2')
        False

        Equality works as per regular string rules:
        >>> N('a1b2c3') == N('a1b2c3')
        True

    """

    PATTERN = re.compile(r'(\d+)')

    def __init__(self, value):
        self.value = tuple(
            int(item) if item.isdigit() else item
            for item in self.PATTERN.split(value)
            # remove empty strings if value ends with a digit
            if item
        )

    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        for this, that in zip_longest(self.value, other.value):
            if this is None:
                return True
            if that is None:
                return False
            this_isstr = isinstance(this, str)
            that_isstr = isinstance(that, str)
            if this_isstr and that_isstr:
                if this == that:
                    continue
                return this < that
            this_isint = isinstance(this, int)
            that_isint = isinstance(that, int)
            if this_isint and that_isint:
                if this == that:
                    continue
                return this < that
            if this_isint and that_isstr:
                return True
            if this_isstr and that_isint:
                return False
        return False


def dummy_flow(data):
    return add_node(
        'workflow',
        data['id'],
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
            ' ',
            (f'job_{state}', str(state_totals[state])),
            (f'job_{state}', JOB_ICON)
        ]
        for state, colour in JOB_COLOURS.items()
        if state in state_totals
        if state_totals[state]
    ]


def get_workflow_status_str(flow):
    """Return a workflow status string for the header.

    Arguments:
        flow (dict):
            GraphQL JSON response for this workflow.

    Returns:
        list - Text list for the urwid.Text widget.

    """


def _render_user(node, data):
    return f'~{ME}'


def _render_job_info(node, data):
    key_len = max(len(key) for key in data)
    ret = [
        f'{key} {" " * (key_len - len(key))} {value}\n'
        for key, value in data.items()
    ]
    ret[-1] = ret[-1][:-1]  # strip trailing newline
    return ret


def _render_job(node, data):
    return [
        f'#{data["submitNum"]:02d} ',
        get_job_icon(data['state'])
    ]


def _render_task(node, data):
    start_time = None
    mean_time = None
    try:
        # due to sorting this is the most recent job
        first_child = node.get_child_node(0)
    except IndexError:
        first_child = None

    # progress information
    if data['state'] == TASK_STATUS_RUNNING and first_child:
        start_time = first_child.get_value()['data']['startedTime']
        mean_time = data['task']['meanElapsedTime']

    # the task icon
    ret = get_task_icon(
        data['state'],
        is_held=data['isHeld'],
        is_queued=data['isQueued'],
        is_runahead=data['isRunahead'],
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


def _render_family(node, data):
    return [
        get_task_icon(
            data['state'],
            is_held=data['isHeld'],
            is_queued=data['isQueued'],
            is_runahead=data['isRunahead']
        ),
        ' ',
        Tokens(data['id']).pop_token()[1]
    ]


def _render_unknown(node, data):
    try:
        state_totals = get_task_status_summary(data)
        status = data['status']
        status_msg = [
            (
                'title',
                _display_workflow_id(data),
            ),
            ' - ',
            (
                f'workflow_{status}',
                status
            )
        ]
    except KeyError:
        return Tokens(data['id']).pop_token()[1]

    return [*status_msg, *state_totals]


def _display_workflow_id(data):
    return data['name']


RENDER_FUNCTIONS = {
    'user': _render_user,
    'root': _render_user,
    'job_info': _render_job_info,
    'job': _render_job,
    'task': _render_task,
    'cycle': _render_family,
    'family': _render_family,
}


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
    return RENDER_FUNCTIONS.get(type_, _render_unknown)(node, data)


def extract_context(selection):
    """Return a dictionary of all component types in the selection.

    Args:
        selection (list):
            List of element id's as extracted from the data store / graphql.

    Examples:
        >>> extract_context(['~a/b', '~a/c'])
        {'user': ['a'], 'workflow': ['b', 'c']}

        >>> extract_context(['~a/b//c/d/e']
        ... )  # doctest: +NORMALIZE_WHITESPACE
        {'user': ['a'], 'workflow': ['b'], 'cycle': ['c'],
        'task': ['d'], 'job': ['e']}

        >>> list(extract_context(['root']).keys())
        ['user']

    """
    ret = {}
    for item in selection:
        if item == 'root':
            # special handling for the Tui "root" node
            # (this represents the workflow owner which is always the same as
            # user for Tui)
            ret['user'] = ME
            continue
        tokens = Tokens(item)
        for key, value in tokens.items():
            if (
                value
                and not key.endswith('_sel')  # ignore selectors
            ):
                lst = ret.setdefault(key, [])
                if value not in lst:
                    lst.append(value)
    return ret


def get_text_dimensions(text: str) -> Tuple[int, int]:
    """Return the monospace size of a block of multiline text.

    Examples:
        >>> get_text_dimensions('foo')
        (3, 1)

        >>> get_text_dimensions('''
        ...     foo bar
        ...     baz
        ... ''')
        (11, 3)

        >>> get_text_dimensions('')
        (0, 0)

    """
    lines = text.splitlines()
    return max((0, *(len(line) for line in lines))), len(lines)
