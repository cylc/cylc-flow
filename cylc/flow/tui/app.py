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

from copy import deepcopy
from contextlib import contextmanager
from multiprocessing import Process
import re

import urwid
try:
    from urwid.widget import SelectableIcon
except ImportError:
    # BACK COMPAT: urwid.wimp
    # From: urwid 2.0
    # To: urwid 2.2
    from urwid.wimp import SelectableIcon

from cylc.flow.id import Tokens
from cylc.flow.task_state import (
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
)
import cylc.flow.tui.overlay as overlay
from cylc.flow.tui import (
    Bindings,
    FORE,
    BACK,
    JOB_COLOURS,
    WORKFLOW_COLOURS,
)
from cylc.flow.tui.tree import (
    find_closest_focus,
    translate_collapsing,
    expand_tree,
)
from cylc.flow.tui.updater import (
    Updater,
    get_default_filters,
)
from cylc.flow.tui.util import (
    dummy_flow,
    render_node
)
from cylc.flow.workflow_status import (
    WorkflowStatus,
)


# default workflow / task filters
# (i.e. show everything)
DEFAULT_FILTERS = get_default_filters()


urwid.set_encoding('utf8')  # required for unicode task icons


class TuiWidget(urwid.TreeWidget):
    """Display widget for tree nodes.

    Arguments:
        app (TuiApp):
            Reference to the application.
        node (TuiNode):
            The root tree node.

    """

    # allows leaf nodes to be selectable, otherwise the cursor
    # will skip rows when the user navigates
    unexpandable_icon = SelectableIcon(' ', 0)

    def __init__(self, app, node):
        self.app = app
        self._node = node
        self._innerwidget = None
        self.is_leaf = not node.get_child_keys()
        self.expanded = False
        widget = self.get_indented_widget()
        urwid.WidgetWrap.__init__(self, widget)

    def selectable(self):
        """Return True if this node is selectable.

        Allow all nodes to be selectable apart from job information nodes.

        """
        return self.get_node().get_value()['type_'] != 'job_info'

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
        ret = super().keypress(size, key)
        if ret in ('left',):
            self.expanded = False
            self.update_expanded_icon()
            # return None so that this keypress is not allowed to
            # propagate up the tree
            return
        return key

    def get_indented_widget(self):
        """Override the Urwid method to handle leaf nodes differently."""
        if self.is_leaf:
            self._innerwidget = urwid.Columns(
                [
                    ('fixed', 1, self.unexpandable_icon),
                    self.get_inner_widget()
                ],
                dividechars=1
            )
        return super().get_indented_widget()

    def update_expanded_icon(self, subscribe=True):
        """Update the +/- icon.

        This method overrides the built-in urwid update_expanded_icon method
        in order to add logic for subscribing and unsubscribing to workflows.

        Args:
            subscribe:
                If True, then we will [un]subscribe to workflows when workflow
                nodes are expanded/collapsed. If False, then these events will
                be ignored. Note we set subscribe=False when we are translating
                the expand/collapse status when rebuilding the tree after an
                update.

        """
        if subscribe:
            node = self.get_node()
            value = node.get_value()
            data = value['data']
            type_ = value['type_']
            if type_ == 'workflow':
                if self.expanded:
                    self.app.updater.subscribe(data['id'])
                    self.app.expand_on_load.add(data['id'])
                else:
                    self.app.updater.unsubscribe(data['id'])
        return urwid.TreeWidget.update_expanded_icon(self)


class TuiNode(urwid.ParentNode):
    """Data storage object for Tui tree nodes."""

    def __init__(self, app, *args, **kwargs):
        self.app = app
        urwid.ParentNode.__init__(self, *args, **kwargs)

    def load_widget(self):
        return TuiWidget(self.app, self)

    def load_child_keys(self):
        # Note: keys are really indices.
        return range(len(self.get_value()['children']))

    def load_child_node(self, key):
        """Return a TuiNode instance for child "key"."""
        return TuiNode(
            self.app,
            self.get_value()['children'][key],
            parent=self,
            key=key,
            depth=self.get_depth() + 1
        )


@contextmanager
def updater_subproc(filters, client_timeout):
    """Runs the Updater in its own process.

    The updater provides the data for Tui to render. Running the updater
    in its own process removes its CPU load from the Tui app allowing
    it to remain responsive whilst updates are being gathered as well as
    decoupling the application update logic from the data update logic.
    """
    # start the updater
    updater = Updater(client_timeout=client_timeout)
    p = Process(target=updater.start, args=(filters,))
    try:
        p.start()
        yield updater
    finally:
        updater.terminate()
        p.join(4)  # timeout of 4 seconds
        if p.exitcode is None:
            # updater did not exit within timeout -> kill it
            p.terminate()


class TuiApp:
    """An application to display a single Cylc workflow.

    This is a single workflow view component (purposefully).

    Multi-workflow functionality can be achieved via a GScan-esque
    tab/selection panel.

    Arguments:
        id_ (str):
            Workflow registration

    """

    # the UI update interval
    # NOTE: this is different from the data update interval
    UPDATE_INTERVAL = 0.1

    # colours to be used throughout the application
    palette = [
        ('head', FORE, BACK),
        ('body', FORE, BACK),
        ('foot', 'white', 'dark blue'),
        ('key', 'light cyan', 'dark blue'),
        ('title', 'default, bold', BACK),
        ('header', 'dark gray', BACK),
        ('header_key', 'dark gray, bold', BACK),
        ('overlay', 'black', 'light gray'),
        # cylc logo colours
        ('R', 'light red, bold', BACK),
        ('Y', 'yellow, bold', BACK),
        ('G', 'light green, bold', BACK),
        ('B', 'light blue, bold', BACK),
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

    def __init__(self, screen=None):
        self.loop = None
        self.screen = screen
        self.stack = 0
        self.tree_walker = None

        # store a reference to the bindings on the app to avoid cicular import
        self.bindings = BINDINGS

        # create the template
        topnode = TuiNode(self, dummy_flow({'id': 'Loading...'}))
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(topnode))
        header = urwid.Text('\n')
        footer = urwid.AttrMap(urwid.Text(list_bindings()), 'foot')
        self.view = urwid.Frame(
            urwid.AttrMap(self.listbox, 'body'),
            header=urwid.AttrMap(header, 'head'),
            footer=footer
        )
        self.filters = get_default_filters()

    @contextmanager
    def main(
        self,
        w_id=None,
        id_filter=None,
        interactive=True,
        client_timeout=3,
    ):
        """Start the Tui app.

        With interactive=False, this does not start the urwid event loop to
        make testing more deterministic. If you want Tui to update (i.e.
        display the latest data), you must call the update method manually.

        Note, we still run the updater asynchronously in a subprocess so that
        we can test the interactions between the Tui application and the
        updater processes.

        """
        self.set_initial_filters(w_id, id_filter)

        with updater_subproc(self.filters, client_timeout) as updater:
            self.updater = updater

            # pre-subscribe to the provided workflow if requested
            self.expand_on_load = {w_id or 'root'}
            if w_id:
                self.updater.subscribe(w_id)

            # configure the urwid main loop
            self.loop = urwid.MainLoop(
                self.view,
                self.palette,
                unhandled_input=self.unhandled_input,
                screen=self.screen
            )

            if interactive:
                # Tui is being run normally as an interactive application
                # schedule the first update
                self.loop.set_alarm_in(0, self.update)

                # start the urwid main loop
                try:
                    self.loop.run()
                except KeyboardInterrupt:
                    yield
                    return
            else:
                # wait for the first full update
                self.wait_until_loaded(w_id or 'root')

            yield self

    def set_initial_filters(self, w_id, id_filter):
        """Set the default workflow/task filters on startup."""
        if w_id:
            # Tui has been configured to look at a single workflow
            # => filter everything else out
            workflow = str(Tokens(w_id)['workflow'])
            self.filters['workflows']['id'] = rf'^{re.escape(workflow)}$'
        elif id_filter:
            # a custom workflow ID filter has been provided
            self.filters['workflows']['id'] = id_filter

    def wait_until_loaded(self, *ids, retries=None, max_fails=50):
        """Wait for any requested nodes to be created.

        Warning:
            This method is blocking! It's for HTML / testing purposes only!

        Args:
            ids:
                Iterable containing the node IDs you want to wait for.
                Note, these should be full IDs i.e. they should include the
                user.
                To wait for the root node to load, use "root".
            retries:
                The maximum number of updates to perform whilst waiting
                for the specified IDs to appear in the tree.
            max_fails:
                If there is no update received from the updater, then we call
                it a failed attempt. This isn't necessarily an issue, the
                updater might be running a little slow. But if there are a
                large number of fails, it likely means the condition won't be
                satisfied.

        Returns:
            A list of the IDs which NOT not appear in the store.

        Raises:
            Exception:
                If the "max_fails" are exhausted.

        """
        from time import sleep
        ids = set(ids)
        self.expand_on_load.update(ids)
        successful_updates = 0
        failed_updates = 0
        while ids & self.expand_on_load:
            if self.update():
                successful_updates += 1
                if retries is not None and successful_updates > retries:
                    return list(self.expand_on_load)
            else:
                failed_updates += 1
                if failed_updates > max_fails:
                    raise Exception(
                        f'No update was received after {max_fails} attempts.'
                        f'\nThere were {successful_updates} successful'
                        ' updates.'
                    )

            sleep(0.15)  # blocking to Tui but not to the updater process
        return None

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

    @staticmethod
    def get_node_id(node):
        """Return a unique identifier for a node.

        Arguments:
            node (TuiNode): The node.

        Returns:
            str - Unique identifier

        """
        return node.get_value()['id_']

    def update_header(self):
        """Update the application header."""
        header = [
            # the Cylc Tui logo
            ('R', 'C'),
            ('Y', 'y'),
            ('G', 'l'),
            ('B', 'c'),
            ('title', ' Tui')
        ]
        if self.filters['tasks'] != DEFAULT_FILTERS['tasks']:
            # if task filters are active, display short help
            header.extend([
                ('header', '   tasks filtered ('),
                ('header_key', 'T'),
                ('header', ' - edit, '),
                ('header_key', 'R'),
                ('header', ' - reset)'),
            ])
        if self.filters['workflows'] != DEFAULT_FILTERS['workflows']:
            # if workflow filters are active, display short help
            header.extend([
                ('header', '   workflows filtered ('),
                ('header_key', 'W'),
                ('header', ' - edit, '),
                ('header_key', 'E'),
                ('header', ' - reset)'),
            ])
        elif self.filters == DEFAULT_FILTERS:
            # if not filters are available show application help
            header.extend([
                ('header', '   '),
                ('header_key', 'h'),
                ('header', ' to show help, '),
                ('header_key', 'q'),
                ('header', ' to quit'),
            ])

        # put in a one line gap
        header.append('\n')

        # replace the previous header
        self.view.header = urwid.Text(header)

    def get_update(self):
        """Fetch the most recent update.

        Returns the update, or False if there is no update queued.
        """
        update = False
        while not self.updater.update_queue.empty():
            # fetch the most recent update
            update = self.updater.update_queue.get()
        return update

    def update(self, *_):
        """Refresh the data and redraw this widget.

        Preserves the current focus and collapse/expand state.

        """
        # attempt to fetch an update
        update = self.get_update()
        if update is False:
            # there was no update, try again later
            if self.loop:
                self.loop.set_alarm_in(self.UPDATE_INTERVAL, self.update)
            return False

        # update the application header
        self.update_header()

        # global update - the nuclear option - slow but simple
        # TODO: this can be done incrementally by adding and
        #       removing nodes from the existing tree
        topnode = TuiNode(self, update)

        # NOTE: because we are nuking the tree we need to manually
        # preserve the focus and collapse status of tree nodes

        # record the old focus
        _, old_node = self.listbox.body.get_focus()

        # nuke the tree
        self.tree_walker = urwid.TreeWalker(topnode)
        self.listbox.body = self.tree_walker

        # get the new focus
        _, new_node = self.listbox.body.get_focus()

        # preserve the focus or walk to the nearest parent
        closest_focus = find_closest_focus(self, old_node, new_node)
        self.listbox.body.set_focus(closest_focus)

        #  preserve the collapse/expand status of all nodes
        translate_collapsing(self, old_node, new_node)

        # expand any nodes which have been requested
        for id_ in list(self.expand_on_load):
            depth = 1 if id_ == 'root' else None
            if expand_tree(self, new_node, id_, depth):
                self.expand_on_load.remove(id_)

        # schedule the next run of this update method
        if self.loop:
            self.loop.set_alarm_in(self.UPDATE_INTERVAL, self.update)

        return True

    def filter_by_task_state(self, filtered_state=None):
        """Filter tasks.

        Args:
            filtered_state (str):
                A task state to filter by or None.

        """
        self.filters['tasks'] = {
            state: (state == filtered_state) or not filtered_state
            for state in self.filters['tasks']
        }
        self.updater.update_filters(self.filters)

    def reset_workflow_filters(self):
        """Reset workflow state/id filters."""
        self.filters['workflows'] = deepcopy(DEFAULT_FILTERS['workflows'])
        self.updater.update_filters(self.filters)

    def filter_by_workflow_state(self, *filtered_states):
        """Filter workflows.

        Args:
            filtered_state (str):
                A task state to filter by or None.

        """
        for state in self.filters['workflows']:
            if state != 'id':
                self.filters['workflows'][state] = (
                    (state in filtered_states) or not filtered_states
                )
        self.updater.update_filters(self.filters)

    def open_overlay(self, fcn):
        """Open an overlay over the application.

        Args:
            fcn: A function which returns an urwid widget to overlay.

        """
        self.create_overlay(*fcn(app=self))

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
        # create the overlay
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

        # add it into the overlay stack
        self.loop.widget = overlay
        self.stack += 1

        # force urwid to render the overlay now rather than waiting until the
        # event loop becomes idle
        self.loop.draw_screen()

    def close_topmost(self):
        """Remove the topmost frame or uit the app if none present."""
        if self.stack <= 0:
            raise urwid.ExitMainLoop()
        self.loop.widget = self.loop.widget[0]
        self.stack -= 1


# register key bindings
# * all bindings must belong to a group
# * all keys are auto-documented in the help screen and application footer
BINDINGS = Bindings()
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
    'filter tasks',
    'Filter by task state'
)
BINDINGS.bind(
    ('T',),
    'filter tasks',
    'Select task states to filter by',
    (TuiApp.open_overlay, overlay.filter_task_state)
)
BINDINGS.bind(
    ('f',),
    'filter tasks',
    'Show only failed tasks',
    (TuiApp.filter_by_task_state, TASK_STATUS_FAILED)
)
BINDINGS.bind(
    ('s',),
    'filter tasks',
    'Show only submitted tasks',
    (TuiApp.filter_by_task_state, TASK_STATUS_SUBMITTED)
)
BINDINGS.bind(
    ('r',),
    'filter tasks',
    'Show only running tasks',
    (TuiApp.filter_by_task_state, TASK_STATUS_RUNNING)
)
BINDINGS.bind(
    ('R',),
    'filter tasks',
    'Reset task state filtering',
    (TuiApp.filter_by_task_state,)
)

BINDINGS.add_group(
    'filter workflows',
    'Filter by workflow state'
)
BINDINGS.bind(
    ('W',),
    'filter workflows',
    'Select workflow states to filter by',
    (TuiApp.open_overlay, overlay.filter_workflow_state)
)
BINDINGS.bind(
    ('E',),
    'filter workflows',
    'Reset workflow filtering',
    (TuiApp.reset_workflow_filters,)
)
BINDINGS.bind(
    ('p',),
    'filter workflows',
    'Show only running workflows',
    (
        TuiApp.filter_by_workflow_state,
        WorkflowStatus.RUNNING.value,
        WorkflowStatus.PAUSED.value,
        WorkflowStatus.STOPPING.value
    )
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
