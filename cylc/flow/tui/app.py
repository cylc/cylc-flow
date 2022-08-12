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
"""The application control logic for Tui."""

import sys

import urwid
from urwid import html_fragment
from urwid.wimp import SelectableIcon
from pathlib import Path

from cylc.flow.network.client_factory import get_client
from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    WorkflowStopped
)
from cylc.flow.pathutil import get_workflow_run_dir
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
)
from cylc.flow.tui.data import (
    QUERY
)
import cylc.flow.tui.overlay as overlay
from cylc.flow.tui import (
    BINDINGS,
    FORE,
    BACK,
    JOB_COLOURS,
    WORKFLOW_COLOURS,
)
from cylc.flow.tui.tree import (
    find_closest_focus,
    translate_collapsing
)
from cylc.flow.tui.util import (
    compute_tree,
    dummy_flow,
    get_task_status_summary,
    get_workflow_status_str,
    render_node
)
from cylc.flow.workflow_files import WorkflowFiles


urwid.set_encoding('utf8')  # required for unicode task icons

TREE_EXPAND_DEPTH = [2]


class TuiWidget(urwid.TreeWidget):
    """Display widget for tree nodes.

    Arguments:
        node (TuiNode):
            The root tree node.
        max_depth (int):
            Determines which nodes are unfolded by default.
            The maximum tree depth to unfold.

    """

    # allows leaf nodes to be selectable, otherwise the cursor
    # will skip rows when the user navigates
    unexpandable_icon = SelectableIcon(' ', 0)

    def __init__(self, node, max_depth=None):
        if not max_depth:
            max_depth = TREE_EXPAND_DEPTH[0]
        self._node = node
        self._innerwidget = None
        self.is_leaf = not node.get_child_keys()
        if max_depth > 0:
            self.expanded = node.get_depth() < max_depth
        else:
            self.expanded = True
        widget = self.get_indented_widget()
        urwid.WidgetWrap.__init__(self, widget)

    def selectable(self):
        """Return True if this node is selectable.

        Allow all nodes to be selectable apart from job information nodes.

        """
        return self.get_node().get_value()['type_'] != 'job_info'

    def _is_leaf(self):
        """Return True if this node has no children

        Note: the `is_leaf` attribute doesn't seem to give the right
              answer.

        """
        return (
            not hasattr(self, 'git_first_child')
            or not self.get_first_child()
        )

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
        return render_node(node, data, type_)

    def keypress(self, size, key):
        """Handle expand & collapse requests.

        Overridden from urwid.TreeWidget to change the behaviour
        of the left arrow key which urwid uses for navigation
        but which we think should be used for collapsing.

        """
        ret = self.__super.keypress(size, key)
        if ret in ('left',):
            self.expanded = False
            self.update_expanded_icon()
            # return None so that this keypress is not allowed to
            # propagate up the tree
            return
        return key

    def get_indented_widget(self):
        if self.is_leaf:

            self._innerwidget = urwid.Columns(
                [
                    ('fixed', 1, self.unexpandable_icon),
                    self.get_inner_widget()
                ],
                dividechars=1
            )
        return self.__super.get_indented_widget()


class TuiNode(urwid.TreeNode):
    """Data storage object for leaf nodes."""

    def load_widget(self):
        return TuiWidget(self)


class TuiParentNode(urwid.ParentNode):
    """Data storage object for interior/parent nodes."""

    def load_widget(self):
        return TuiWidget(self)

    def load_child_keys(self):
        # Note: keys are really indices.
        data = self.get_value()
        return range(len(data['children']))

    def load_child_node(self, key):
        """Return either an TuiNode or TuiParentNode"""
        childdata = self.get_value()['children'][key]
        if 'children' in childdata:
            childclass = TuiParentNode
        else:
            childclass = TuiNode
        return childclass(
            childdata,
            parent=self,
            key=key,
            depth=self.get_depth() + 1
        )


class TuiApp:
    """An application to display a single Cylc workflow.

    This is a single workflow view component (purposefully).

    Multi-workflow functionality can be achieved via a GScan-esque
    tab/selection panel.

    Arguments:
        reg (str):
            Workflow registration

    """

    UPDATE_INTERVAL = 1
    CLIENT_TIMEOUT = 1

    palette = [
        ('head', FORE, BACK),
        ('body', FORE, BACK),
        ('foot', 'white', 'dark blue'),
        ('key', 'light cyan', 'dark blue'),
        ('title', FORE, BACK, 'bold'),
        ('overlay', 'black', 'light gray'),
    ] + [  # job colours
        (f'job_{status}', colour, BACK)
        for status, colour in JOB_COLOURS.items()
    ] + [  # job colours for help screen
        (f'overlay_job_{status}', colour, 'light gray')
        for status, colour in JOB_COLOURS.items()
    ] + [  # workflow state colours
        (f'workflow_{status}',) + spec
        for status, spec in WORKFLOW_COLOURS.items()
    ]

    def __init__(self, reg, screen=None):
        self.reg = reg
        self.client = None
        self.loop = None
        self.screen = None
        self.stack = 0
        self.tree_walker = None

        # create the template
        topnode = TuiParentNode(dummy_flow({'id': 'Loading...'}))
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(topnode))
        header = urwid.Text('\n')
        footer = urwid.AttrWrap(
            # urwid.Text(self.FOOTER_TEXT),
            urwid.Text(list_bindings()),
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
        self.loop.set_alarm_in(0, self._update)
        self.loop.run()

    def unhandled_input(self, key):
        """Catch key presses, uncaught events are passed down the chain."""
        if key in ('ctrl d',):
            raise urwid.ExitMainLoop()
        for binding in BINDINGS:
            # iterate through key bindings in order
            if key in binding['keys'] and binding['callback']:
                # if we get a match execute the callback
                # NOTE: if there is no callback then this binding is
                #       for documentation purposes only so we ignore it
                meth, *args = binding['callback']
                meth(self, *args)
                return

    def get_snapshot(self):
        """Contact the workflow, return a tree structure

        In the event of error contacting the workflow the
        message is written to this Widget's header.

        Returns:
            dict if successful, else False

        """
        try:
            if not self.client:
                self.client = get_client(self.reg, timeout=self.CLIENT_TIMEOUT)
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
        except WorkflowStopped:
            # Distinguish stopped flow from non-existent flow.
            self.client = None
            full_path = Path(get_workflow_run_dir(self.reg))
            if (
                (full_path / WorkflowFiles.SUITE_RC).is_file()
                or (full_path / WorkflowFiles.FLOW_FILE).is_file()
            ):
                message = "stopped"
            else:
                message = (
                    f"No {WorkflowFiles.SUITE_RC} or {WorkflowFiles.FLOW_FILE}"
                    f"found in {self.reg}."
                )

            return dummy_flow({
                'name': self.reg,
                'id': self.reg,
                'status': message,
                'stateTotals': {}
            })
        except (ClientError, ClientTimeout) as exc:
            # catch network / client errors
            self.set_header([('workflow_error', str(exc))])
            return False

        if isinstance(data, list):
            # catch GraphQL errors
            try:
                message = data[0]['error']['message']
            except (IndexError, KeyError):
                message = str(data)
            self.set_header([('workflow_error', message)])
            return False

        if len(data['workflows']) != 1:
            # multiple workflows in returned data - shouldn't happen
            raise ValueError()

        return compute_tree(data['workflows'][0])

    @staticmethod
    def get_node_id(node):
        """Return a unique identifier for a node.

        Arguments:
            node (TuiNode): The node.

        Returns:
            str - Unique identifier

        """
        return node.get_value()['id_']

    def set_header(self, message: list):
        """Set the header message for this widget.

        Arguments:
            message (object):
                Text content for the urwid.Text widget,
                may be a string, tuple or list, see urwid docs.

        """
        # put in a one line gap
        message.append('\n')

        # TODO: remove once Tui is delta-driven
        # https://github.com/cylc/cylc-flow/issues/3527
        message.extend([
            (
                'workflow_error',
                'TUI is experimental and may break with large flows'
            ),
            '\n'
        ])

        self.view.header = urwid.Text(message)

    def _update(self, *_):
        try:
            self.update()
        except Exception as exc:
            sys.exit(exc)

    def update(self):
        """Refresh the data and redraw this widget.

        Preserves the current focus and collapse/expand state.

        """
        # update the data store
        # TODO: this can be done incrementally using deltas
        #       once this interface is available
        snapshot = self.get_snapshot()
        if snapshot is False:
            return False

        # update the workflow status message
        header = [get_workflow_status_str(snapshot['data'])]
        status_summary = get_task_status_summary(snapshot['data'])
        if status_summary:
            header.extend([' ('] + status_summary + [' )'])
        if not all(self.filter_states.values()):
            header.extend([' ', '*filtered* "R" to reset', ' '])
        self.set_header(header)

        # global update - the nuclear option - slow but simple
        # TODO: this can be done incrementally by adding and
        #       removing nodes from the existing tree
        topnode = TuiParentNode(snapshot)

        # NOTE: because we are nuking the tree we need to manually
        # preserve the focus and collapse status of tree nodes

        # record the old focus
        _, old_node = self.listbox._body.get_focus()

        # nuke the tree
        self.tree_walker = urwid.TreeWalker(topnode)
        self.listbox._set_body(self.tree_walker)

        # get the new focus
        _, new_node = self.listbox._body.get_focus()

        # preserve the focus or walk to the nearest parent
        closest_focus = find_closest_focus(self, old_node, new_node)
        self.listbox._body.set_focus(closest_focus)

        #  preserve the collapse/expand status of all nodes
        translate_collapsing(self, old_node, new_node)

        # schedule the next run of this update method
        if self.loop:
            self.loop.set_alarm_in(self.UPDATE_INTERVAL, self._update)

        return True

    def filter_by_task_state(self, filtered_state=None):
        """Filter tasks.

        Args:
            filtered_state (str):
                A task state to filter by or None.

        """
        self.filter_states = {
            state: (state == filtered_state) or not filtered_state
            for state in self.filter_states
        }
        return

    def open_overlay(self, fcn):
        self.create_overlay(*fcn(self))

    def create_overlay(self, widget, kwargs):
        """Open an overlay over the monitor.

        Args:
            widget (urwid.Widget):
                Widget to be placed inside the overlay.
            kwargs (dict):
                Dictionary of arguments to pass to the `urwid.Overlay`
                constructor.

                You will likely need to set `width` and `height` here.

                See `urwid` docs for details.

        """
        kwargs = {'width': 'pack', 'height': 'pack', **kwargs}
        overlay = urwid.Overlay(
            urwid.LineBox(
                urwid.AttrMap(
                    urwid.Frame(
                        urwid.Padding(
                            widget,
                            left=2,
                            right=2
                        ),
                        footer=urwid.Text('\n q to close')
                    ),
                    'overlay',
                )
            ),
            self.loop.widget,
            align='center',
            valign='middle',
            left=self.stack * 5,
            top=self.stack * 5,
            **kwargs,
        )
        self.loop.widget = overlay
        self.stack += 1

    def close_topmost(self):
        """Remove the topmost frame or uit the app if none present."""
        if self.stack <= 0:
            raise urwid.ExitMainLoop()
        self.loop.widget = self.loop.widget[0]
        self.stack -= 1


BINDINGS.add_group(
    '',
    'Application Controls'
)
BINDINGS.bind(
    ('q',),
    '',
    'Quit',
    (TuiApp.close_topmost,)
)
BINDINGS.bind(
    ('h',),
    '',
    'Help',
    (TuiApp.open_overlay, overlay.help_info)
)
BINDINGS.bind(
    ('enter',),
    '',
    'Context',
    (TuiApp.open_overlay, overlay.context)
)

BINDINGS.add_group(
    'tree',
    'Expand/Collapse nodes',
)
BINDINGS.bind(
    ('-', '\u2190'),
    'tree',
    'Collapse',
    None  # this binding is for documentation only - handled by urwid
)
BINDINGS.bind(
    ('+', '\u2192'),
    'tree',
    'Expand',
    None  # this binding is for documentation only - handled by urwid
)

BINDINGS.add_group(
    'navigation',
    'Move within the tree'
)
BINDINGS.bind(
    ('\u2191',),
    'navigation',
    'Up',
    None  # this binding is for documentation only - handled by urwid
)
BINDINGS.bind(
    ('\u2193',),
    'navigation',
    'Down',
    None  # this binding is for documentation only - handled by urwid
)
BINDINGS.bind(
    ('\u21a5',),
    'navigation',
    'PageUp',
    None  # this binding is for documentation only - handled by urwid
)
BINDINGS.bind(
    ('\u21a7',),
    'navigation',
    'PageDown',
    None  # this binding is for documentation only - handled by urwid
)
BINDINGS.bind(
    ('Home',),
    'navigation',
    'Top',
    None  # this binding is for documentation only - handled by urwid
)
BINDINGS.bind(
    ('End',),
    'navigation',
    'Bottom',
    None  # this binding is for documentation only - handled by urwid
)

BINDINGS.add_group(
    'filter',
    'Filter by task state'
)
BINDINGS.bind(
    ('F',),
    'filter',
    'Select task states to filter by',
    (TuiApp.open_overlay, overlay.filter_task_state)
)
BINDINGS.bind(
    ('f',),
    'filter',
    'Show only failed tasks',
    (TuiApp.filter_by_task_state, TASK_STATUS_FAILED)
)
BINDINGS.bind(
    ('s',),
    'filter',
    'Show only submitted tasks',
    (TuiApp.filter_by_task_state, TASK_STATUS_SUBMITTED)
)
BINDINGS.bind(
    ('r',),
    'filter',
    'Show only running tasks',
    (TuiApp.filter_by_task_state, TASK_STATUS_RUNNING)
)
BINDINGS.bind(
    ('R',),
    'filter',
    'Reset task state filtering',
    (TuiApp.filter_by_task_state,)
)


def list_bindings():
    """Write out an in-line list of the key bindings."""
    ret = []
    for group, bindings in BINDINGS.list_groups():
        if group['name']:
            ret.append(f' {group["name"]}: ')
            for binding in bindings:
                for key in binding['keys']:
                    ret.append(('key', f'{key} '))
        else:
            # list each option in the default group individually
            for binding in bindings:
                ret.append(f'{binding["desc"].lower()}: ')
                ret.append(('key', binding["keys"][0]))
                ret.append(' ')
                ret.append(' ')
            ret.pop()  # remove surplus space
    return ret
