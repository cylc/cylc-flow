#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""cylc [task] tui REG

Open the terminal user interface (TUI) for the given suite.

                               _,@@@@@@.
                             <=@@@, `@@@@@.
                                `-@@@@@@@@@@@'
                                   :@@@@@@@@@@.
                                    .@@@@@@@@@@@
                                   '@@@@@@@@@@@@.
                                ;.@@@@@@@@@@@@@@@
                              '@@@@@@@@@@@@@@@@@@,
                            ,@@@@@@@@@@@@@@@@@@@@'
                          :.@@@@@@@@@@@@@@@@@@@@@.
                        .@@@@@@@@@@@@@@@@@@@@@@@@.
                      '@@@@@@@@@@@@@@@@@@@@@@@@@.
                    ;@@@@@@@@@@@@@@@@@@@@@@@@@@@
                   .@@@@@@@@@@@@@@@@@@@@@@@@@@.
                  .@@@@@@@@@@@@@@@@@@@@@@@@@@,
                 .@@@@@@@@@@@@@@@@@@@@@@@@@'
                .@@@@@@@@@@@@@@@@@@@@@@@@'     ,
              :@@@@@@@@@@@@@@@@@@@@@..''';,,,;::-
             '@@@@@@@@@@@@@@@@@@@.        `.   `
            .@@@@@@.: ,.@@@@@@@.            `
          :@@@@@@@,         ;.@,
         '@@@@@@.              `@'
        .@@@@@@;                ;-,
     ;.@@@@@@.                    ...,
    ,,; ,;;                      ;  ',
                                      ;;

"""

from functools import partial
import sys
from time import time

import urwid
from urwid import html_fragment

from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout
)
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_DISPLAY_ORDER,
    TASK_STATUS_RUNAHEAD,
    TASK_STATUS_WAITING,
    TASK_STATUS_QUEUED,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_READY,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RETRYING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED
)
from cylc.flow.terminal import cli_function
from cylc.flow.wallclock import get_unix_time_from_time_string


if "--use-ssh" in sys.argv[1:]:
    # requires local terminal
    sys.exit("No '--use-ssh': this command requires a local terminal.")

urwid.set_encoding('utf8')  # required for unicode task icons

# default foreground and background colours
# NOTE: set to default to allow user defined terminal theming
FORE = 'default'
BACK = 'default'

SUITE_COLOURS = {
    'running': ('light blue', BACK),
    'held': ('brown', BACK),
    'stopping': ('light magenta', BACK),
    'error': ('light red', BACK, 'bold')
}

TASK_ICONS = {
    f'{TASK_STATUS_WAITING}': '\u25cb',

    # TODO: remove with https://github.com/cylc/cylc-admin/pull/47
    f'{TASK_STATUS_READY}': '\u25cb',
    f'{TASK_STATUS_QUEUED}': '\u25cb',
    f'{TASK_STATUS_RETRYING}': '\u25cb',
    f'{TASK_STATUS_SUBMIT_RETRYING}': '\u25cb',
    # TODO: remove with https://github.com/cylc/cylc-admin/pull/47

    f'{TASK_STATUS_SUBMITTED}': '\u2299',
    f'{TASK_STATUS_RUNNING}': '\u2299',
    f'{TASK_STATUS_RUNNING}:0': '\u2299',
    f'{TASK_STATUS_RUNNING}:25': '\u25D4',
    f'{TASK_STATUS_RUNNING}:50': '\u25D1',
    f'{TASK_STATUS_RUNNING}:75': '\u25D5',
    f'{TASK_STATUS_SUCCEEDED}': '\u25CF',
    f'{TASK_STATUS_EXPIRED}': '\u25CF',
    f'{TASK_STATUS_SUBMIT_FAILED}': '\u2297',
    f'{TASK_STATUS_FAILED}': '\u2297'
}

TASK_MODIFIERS = {
    'held': '\u030E'
}

JOB_ICON = '\u25A0'

JOB_COLOURS = {
    'submitted': 'dark cyan',
    'running': 'light blue',
    'succeeded': 'dark green',
    'failed': 'light red',
    'submit-failed': 'light magenta',

    # TODO: update with https://github.com/cylc/cylc-admin/pull/47
    'ready': 'brown'
    # TODO: update with https://github.com/cylc/cylc-admin/pull/47
}

TREE_EXPAND_DEPTH = [2]

QUERY = '''
  query cli($taskStates: [String]){
    workflows {
      id
      name
      status
      stateTotals
      taskProxies(states: $taskStates) {
        id
        name
        cyclePoint
        state
        isHeld
        parents {
          id
          name
        }
        jobs {
          id
          submitNum
          state
          host
          batchSysName
          batchSysJobId
          startedTime
        }
        task {
          meanElapsedTime
        }
      }
      familyProxies(states: $taskStates) {
        id
        name
        cyclePoint
        state
        isHeld
        firstParent {
          id
          name
        }
      }
    }
  }
'''


def intersperse(lst, fill):
    """Return list with `fill` inbetween every item of `lst`.

    Example:
        >>> intersperse([1, 2, 3], 0)
        [1, 0, 2, 0, 3]

    """
    ret = [fill] * (len(lst) * 2 - 1)
    ret[0::2] = lst
    return ret


def _get_display_text(node, data, type_):
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

    if type_ == 'family':
        return [
            get_task_icon(
                data['state'],
                data['isHeld']
            ),
            ' ',
            data['id'].rsplit('|', 1)[-1]
        ]

    return data['id'].rsplit('|', 1)[-1]


class MonitorWidget(urwid.TreeWidget):
    """Display widget for leaf nodes.

    Arguments:
        node (MonitorNode):
            The root tree node.
        max_depth (int):
            Determines which nodes are unfolded by default.
            The maximum tree depth to unfold.

    """

    def __init__(self, node, max_depth=None):
        # NOTE: copy of urwid.TreeWidget.__init__, the only difference
        #       being the self.expanded logic
        if not max_depth:
            max_depth = TREE_EXPAND_DEPTH[0]
        self._node = node
        self._innerwidget = None
        self.is_leaf = not hasattr(node, 'get_first_child')
        if max_depth > 0:
            self.expanded = node.get_depth() < max_depth
        else:
            self.expanded = True
        widget = self.get_indented_widget()
        urwid.WidgetWrap.__init__(self, widget)

    def get_display_text(self):
        """Compute the text to display for a given node.

        Returns:
            (object) - Text content for the urwid.Text widget,
            may be a string, tuple or list, see urwid docs.

        """
        node = self.get_node()
        value = node.get_value()
        data = value['data']
        type_ = value['type_']
        return _get_display_text(node, data, type_)


class MonitorNode(urwid.TreeNode):
    """Data storage object for leaf nodes."""

    def load_widget(self):
        return MonitorWidget(self)


class MonitorParentNode(urwid.ParentNode):
    """Data storage object for interior/parent nodes."""

    def load_widget(self):
        return MonitorWidget(self)

    def load_child_keys(self):
        # Note: keys are really indices.
        data = self.get_value()
        return range(len(data['children']))

    def load_child_node(self, key):
        """Return either an MonitorNode or MonitorParentNode"""
        childdata = self.get_value()['children'][key]
        if 'children' in childdata:
            childclass = MonitorParentNode
        else:
            childclass = MonitorNode
        return childclass(
            childdata,
            parent=self,
            key=key,
            depth=self.get_depth() + 1
        )


class MonitorTreeBrowser:
    """An application to display a single Cylc workflow.

    This is a single workflow view component (purposefully).

    Multi-suite functionality can be achieved via a GScan-esque
    tab/selection panel.

    Arguments:
        client (cylc.network.client.SuiteRuntimeClient):
            A suite client we can request data from.

    """

    UPDATE_INTERVAL = 1

    palette = [
        ('head', FORE, BACK),
        ('body', FORE, BACK),
        ('foot', 'white', 'dark blue'),
        ('key', 'light cyan', 'dark blue'),
        ('title', FORE, BACK, 'bold'),
        ('overlay', 'black', 'light gray'),
    ] + [
        (f'job_{status}', colour, BACK)
        for status, colour in JOB_COLOURS.items()
    ] + [
        (f'suite_{status}',) + spec
        for status, spec in SUITE_COLOURS.items()
    ]

    FOOTER_TEXT = intersperse(
        [
            'navigation:',
            ('key', '\u2191'),
            ('key', '\u2193'),
            ('key', '\u2190'),
            ('key', '\u21a5'),
            ('key', '\u21a7'),
            ('key', 'Home'),
            ('key', 'End'),
            ' expand:',
            ('key', '+'),
            ('key', '-'),
            ' exit:',
            ('key', 'q'),
            ' filter: ',
            ('key', 'F'),
            ('key', 'R'),
            ('key', 'f'),
            ('key', 's'),
            ('key', 'r'),
        ],
        # stick a space between every item in th preceding list
        ' '
    )

    def __init__(self, client, screen=None):
        # the cylc data client
        self.client = client
        self.loop = None
        self.screen = None

        # create the template
        topnode = MonitorParentNode(dummy_flow())
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(topnode))
        header = urwid.Text('\n')
        footer = urwid.AttrWrap(
            urwid.Text(self.FOOTER_TEXT),
            'foot'
        )
        self.view = urwid.Frame(
            urwid.AttrWrap(self.listbox, 'body'),
            header=urwid.AttrWrap(header, 'head'),
            footer=footer
        )
        self.filter_states = {
            state: True
            for state in TASK_STATUSES_ORDERED
            if state is not TASK_STATUS_RUNAHEAD
        }
        if isinstance(screen, html_fragment.HtmlGenerator):
            # the HtmlGenerator only captures one frame
            # so we need to pre-populate the GUI before
            # starting the event loop
            self.update()

    def main(self):
        """Start the event loop."""
        self.loop = urwid.MainLoop(
            self.view,
            self.palette,
            unhandled_input=self.unhandled_input,
            screen=self.screen
        )
        # schedule the first update
        self.loop.set_alarm_in(0, self.update)
        self.loop.run()

    def unhandled_input(self, key):
        if key in ('q', 'Q') and isinstance(self.loop.widget, urwid.Overlay):
            self.remove_overlay()
            return
        if key in ('q', 'Q', 'ctrl d'):
            raise urwid.ExitMainLoop()
        if key in ('F',):
            self.filter_menu()
            return
        if key in ('R',):
            self.filter_states = {
                state: True
                for state in self.filter_states
            }
            return

        filter_map = {
            'f': TASK_STATUS_FAILED,
            's': TASK_STATUS_SUBMITTED,
            'r': TASK_STATUS_RUNNING
        }

        if key in filter_map:
            filtered_state = filter_map[key]
            self.filter_states = {
                state: state == filtered_state
                for state in self.filter_states
            }
            return

    def get_snapshot(self):
        """Contact the workflow, return a tree structure

        In the event of error contacting the suite the
        message is written to this Widget's header.

        Returns:
            dict if successful, else False

        """
        try:
            data = self.client(
                'graphql',
                {
                    'request_string': QUERY,
                    'variables': {
                        # list of task states we want to see
                        'taskStates': [
                            state
                            for state, is_on in self.filter_states.items()
                            if is_on
                        ]
                    }
                }
            )
        except (ClientError, ClientTimeout) as exc:
            # catch network / client errors
            self.set_header(('suite_error', str(exc)))
            return False

        if isinstance(data, list):
            # catch GraphQL errors
            try:
                message = data[0]['error']['message']
            except (IndexError, KeyError):
                message = str(data)
            self.set_header(('suite_error', message))
            return False

        if len(data['workflows']) != 1:
            # multiple workflows in returned data - shouldn't happen
            raise ValueError()

        return compute_tree(data['workflows'][0])

    @staticmethod
    def get_node_id(node):
        """Return a unique identifier for a node.

        Arguments:
            node (MonitorNode): The node.

        Returns:
            str - Unique identifier

        """
        return node.get_value()['id_']

    def find_closest_focus(self, old_node, new_node):
        """Return the position of the old node in the new tree.

        1. Attempts to find the old node in the new tree.
        2. Otherwise it walks up the old tree until it
           finds a node which is present in the new tree.
        3. Otherwise it returns the root node of the new tree.

        Arguments:
            old_node (MonitiorNode):
                The in-focus node from the deceased tree.
            new_node (MonitorNode):
                The root node from the new tree.

        Returns
            MonitorNode - The closest node.

        """
        old_key = self.get_node_id(old_node)

        for node in self.walk_tree(new_node):
            if old_key == self.get_node_id(node):
                # (1)
                return node

        if not old_node._parent:
            # (3) reset focus
            return new_node

        # (2)
        return self.find_closest_focus(
            old_node._parent,
            new_node
        )

    @staticmethod
    def walk_tree(node):
        """Yield nodes in order.

        Arguments:
            node (urwid.TreeNode):
                Yield this node and all nodes beneath it.

        Yields:
            urwid.TreeNode

        """
        stack = [node]
        while stack:
            node = stack.pop()
            yield node
            stack.extend([
                node.get_child_node(index)
                for index in node.get_child_keys()
            ])

    def translate_collapsing(self, old_node, new_node):
        """Transfer the collapse state from one tree to another.

        Arguments:
            old_node (MonitorNode):
                Any node in the tree you want to copy the
                collapse/expand state from.
            new_node (MonitorNode):
                Any node in the tree you want to copy the
                collapse/expand state to.

        """
        old_root = old_node.get_root()
        new_root = new_node.get_root()

        old_tree = {
            self.get_node_id(node): node.get_widget().expanded
            for node in self.walk_tree(old_root)
        }

        for node in self.walk_tree(new_root):
            key = self.get_node_id(node)
            if key in old_tree:
                expanded = old_tree.get(key)
                widget = node.get_widget()
                if widget.expanded != expanded:
                    widget.expanded = expanded
                    widget.update_expanded_icon()

    @staticmethod
    def get_status_str(flow):
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

    @staticmethod
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
            if state_totals[state]
        ]

    def set_header(self, message):
        """Set the header message for this widget.

        Arguments:
            message (object):
                Text content for the urwid.Text widget,
                may be a string, tuple or list, see urwid docs.

        """
        # put in a one line gap
        if isinstance(message, list):
            message.append('\n')
        elif isinstance(message, tuple):
            message = (message[0], message[1] + '\n')
        else:
            message += '\n'
        self.view.header = urwid.Text(message)

    def update(self, *_):
        """Refresh the data and redraw this widget.

        Preserves the current focus and collapse/expand state.

        """
        # update the data store
        # TODO: this can be done incrementally using deltas
        #       once this interface is available
        snapshot = self.get_snapshot()
        if snapshot is False:
            return False

        # update the suite status message
        self.set_header(
            # suite name and status
            self.get_status_str(snapshot['data'])
            # state totals
            + [' (']
            + self.get_task_status_summary(snapshot['data'])
            + [' )']
            #  filtered message
            + (
                [' *filtered - "R" to reset*']
                if any((
                    not visible
                    for visible in self.filter_states.values()
                ))
                else []
            )
        )

        # global update - the nuclear option - slow but simple
        # TODO: this can be done incrementally by adding and
        #       removing nodes from the existing tree
        topnode = MonitorParentNode(snapshot)

        # NOTE: because we are nuking the tree we need to manually
        # preserve the focus and collapse status of tree nodes

        # record the old focus
        _, old_node = self.listbox._body.get_focus()

        # nuke the tree
        self.listbox._set_body(urwid.TreeWalker(topnode))

        # get the new focus
        _, new_node = self.listbox._body.get_focus()

        # preserve the focus or walk to the nearest parent
        closest_focus = self.find_closest_focus(old_node, new_node)
        self.listbox._body.set_focus(closest_focus)

        # preserve the collapse/expand status of all nodes
        self.translate_collapsing(old_node, new_node)

        # schedule the next run of this update method
        if self.loop:
            self.loop.set_alarm_in(self.UPDATE_INTERVAL, self.update)

        return True

    def filter_menu(self):
        def toggle(state, *_):
            self.filter_states[state] = not self.filter_states[state]
        checkboxes = [
            urwid.CheckBox(
                get_task_icon(state, False)
                + [' ' + state],
                state=is_on,
                on_state_change=partial(toggle, state)
            )
            for state, is_on in self.filter_states.items()
        ]

        def invert(*_):
            for checkbox in checkboxes:
                checkbox.set_state(not checkbox.state)

        overlay = urwid.Overlay(
            urwid.AttrMap(
                urwid.Padding(
                    urwid.ListBox(
                        urwid.SimpleFocusListWalker([
                            urwid.Text('Filter Task States'),
                            urwid.Divider(),
                            urwid.Button(
                                'Invert',
                                on_press=invert
                            )
                        ] + checkboxes + [
                            urwid.Divider(),
                            urwid.Text('"q" to close')
                        ])
                    ),
                    left=2,
                    right=2
                ),
                'overlay',
            ),
            self.loop.widget,
            align='center',
            width=35,
            valign='middle',
            height=18
        )
        self.loop.widget = overlay

    def remove_overlay(self):
        self.loop.widget = self.loop.widget[0]


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

    # create nodes
    for family in flow['familyProxies']:
        if family['name'] != 'root':
            family_node = add_node(
                'family', family['id'], nodes, data=family)
        cycle_data = {
            'name': family['cyclePoint'],
            'id': f"{flow['id']}|{family['cyclePoint']}"
        }
        cycle_node = add_node(
            'cycle', family['cyclePoint'], nodes, data=cycle_data)
        if cycle_node not in flow_node['children']:
            flow_node['children'].append(cycle_node)

    # create cycle/family tree
    for family in flow['familyProxies']:
        if family['name'] != 'root':
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
                cycle_node = add_node(
                    'cycle', family['cyclePoint'], nodes)
                cycle_node['children'].append(family_node)
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
                'cycle', task['cyclePoint'], nodes)
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
        if type_ == 'task':
            node['children'].sort(
                key=lambda x: x['data']['submitNum'],
                reverse=True
            )
        else:
            node['children'].sort(
                key=lambda x: x['id_'],
                reverse=True
            )

    return flow_node


def get_group_state(nodes):
    """Return a task state to represent a collection of tasks.

    Arguments:
        nodes (list):
            List of urwid.TreeNode objects.

    Returns:
        tuple - (status, is_held)

        status (str): A Cylc task status.
        is_held (bool): True if the task is is a held state.

    Raises:
        KeyError:
            If any node does not have the key "state" in its
            data. E.G. a nested family.
        ValueError:
            If no matching states are found. E.G. empty nodes
            list.

    """
    states = [
        node.get_value()['data']['state']
        for node in nodes
    ]
    is_held = any((
        node.get_value()['data'].get('isHeld')
        for node in nodes
    ))
    for state in TASK_STATUS_DISPLAY_ORDER:
        if state in states:
            return state, is_held
    raise ValueError()


def get_task_icon(status, is_held, start_time=None, mean_time=None):
    """Return a Unicode string to represent a task.

    Arguments:
        status (str):
            A Cylc task status string.
        is_held (bool):
            True if the task is in a held state.

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


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            ('REG', 'Suite name')
        ],
        # auto_add=False,  NOTE: at present auto_add can not be turned off
        color=False
    )

    parser.add_option(
        '--display',
        help=(
            'Specify the display technology to use.'
            ' "raw" for interactive in-terminal display.'
            ' "html" for non-interactive html output.'
        ),
        action='store',
        choices=['raw', 'html'],
        default='raw',
    )
    parser.add_option(
        '--v-term-size',
        help=(
            'The virtual terminal size for non-interactive'
            '--display options.'
        ),
        action='store',
        default='80,24'
    )

    return parser


@cli_function(get_option_parser)
def main(_, options, reg):
    screen = None
    if options.display == 'html':
        TREE_EXPAND_DEPTH[0] = -1  # expand tree fully
        screen = html_fragment.HtmlGenerator()
        screen.set_terminal_properties(256)
        screen.register_palette(MonitorTreeBrowser.palette)
        html_fragment.screenshot_init(
            [tuple(map(int, options.v_term_size.split(',')))],
            []
        )

    client = SuiteRuntimeClient(reg)
    MonitorTreeBrowser(client, screen=screen).main()

    if options.display == 'html':
        for fragment in html_fragment.screenshot_collect():
            print(fragment)
