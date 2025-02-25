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
"""Overlay panels for Tui.

Panels are functions::

    function(app) -> (widget, overlay_options)

Parameters:

    app:
        Tui application object.
    widget (urwid.Widget):
        A widget to place in the overlay.
    overlay_options (dict):
        A dictionary of keyword arguments to provide to the
        urwid.Overlay constructor.

        You will likely want to override the `width` and `height`
        arguments.

        See the `urwid` documentation for details.

"""

from functools import partial
import re
import sys

import urwid

from cylc.flow.id import Tokens
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_WAITING
)
from cylc.flow.tui import (
    JOB_COLOURS,
    JOB_ICON,
    TUI
)
from cylc.flow.tui.data import (
    list_mutations,
    mutate,
)
from cylc.flow.tui.util import (
    ListBoxPlus,
    format_flow_nums,
    get_task_icon,
    get_text_dimensions,
)


def _get_display_id(id_):
    """Return an ID for display in context menus.

    * Display the full ID for users/workflows
    * Display the relative ID for everything else

    """
    tokens = Tokens(id_)
    if tokens.is_task_like:
        # if it's a cycle/task/job, then use the relative id
        return tokens.relative_id
    else:
        # otherwise use the full id
        return tokens.id


def _toggle_filter(app, filter_group, status, *_):
    """Toggle a filter state."""
    app.filters[filter_group][status] = not app.filters[filter_group][status]
    app.updater.update_filters(app.filters)


def _invert_filter(checkboxes, *_):
    """Invert the state of all filters."""
    for checkbox in checkboxes:
        checkbox.set_state(not checkbox.state)


def filter_workflow_state(app):
    """Return a widget for adjusting the workflow filter options."""
    checkboxes = [
        urwid.CheckBox(
            [status],
            state=is_on,
            on_state_change=partial(_toggle_filter, app, 'workflows', status)
        )
        for status, is_on in app.filters['workflows'].items()
        if status != 'id'
    ]

    workflow_id_prompt = 'id (regex)'

    def update_id_filter(widget, value):
        nonlocal app
        try:
            # ensure the filter is value before updating the filter
            re.compile(value)
        except re.error:
            # error in the regex -> inform the user
            widget.set_caption(f'{workflow_id_prompt} - error: \n')
        else:
            # valid regex -> update the filter
            widget.set_caption(f'{workflow_id_prompt}: \n')
            app.filters['workflows']['id'] = value
            app.updater.update_filters(app.filters)

    id_filter_widget = urwid.Edit(
        caption=f'{workflow_id_prompt}: \n',
        edit_text=app.filters['workflows']['id'],
    )
    urwid.connect_signal(id_filter_widget, 'change', update_id_filter)

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker([
            urwid.Text('Filter Workflow States'),
            urwid.Divider(),
            urwid.Padding(
                urwid.Button(
                    'Invert',
                    on_press=partial(_invert_filter, checkboxes)
                ),
                right=19
            )
        ] + checkboxes + [
            urwid.Divider(),
            id_filter_widget,
        ])
    )

    return (
        widget,
        {'width': 35, 'height': 23}
    )


def filter_task_state(app):
    """Return a widget for adjusting the task state filter."""

    checkboxes = [
        urwid.CheckBox(
            get_task_icon(state, colour='overlay')
            + [' ' + state],
            state=is_on,
            on_state_change=partial(_toggle_filter, app, 'tasks', state)
        )
        for state, is_on in app.filters['tasks'].items()
    ]

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker([
            urwid.Text('Filter Task States'),
            urwid.Divider(),
            urwid.Padding(
                urwid.Button(
                    'Invert',
                    on_press=partial(_invert_filter, checkboxes)
                ),
                right=19
            )
        ] + checkboxes)
    )

    return (
        widget,
        {'width': 35, 'height': 23}
    )


def help_info(app):
    """Return a widget displaying help information."""
    # system title
    items = [
        urwid.Text(r'''
                   _        _         _
                  | |      | |       (_)
         ___ _   _| | ___  | |_ _   _ _
        / __| | | | |/ __| | __| | | | |
       | (__| |_| | | (__  | |_| |_| | |
        \___|\__, |_|\___|  \__|\__,_|_|
              __/ |
             |___/

          ( scroll using arrow keys )

        '''),
        urwid.Text(TUI)
    ]

    # list key bindings
    for group, bindings in app.bindings.list_groups():
        items.append(
            urwid.Text([
                f'{group["desc"]}:'
            ])
        )
        for binding in bindings:
            keystr = ' '.join(binding['keys'])
            items.append(
                urwid.Text([
                    ('key', keystr),
                    (' ' * (10 - len(keystr))),
                    binding['desc']
                ])
            )
        items.append(
            urwid.Divider()
        )

    # mouse interaction
    items.extend([
        urwid.Text(
            'fn + ⌥ & click to select text' if sys.platform == 'darwin' else
            'Shift & click to select text'
        ),
        urwid.Divider()
    ])

    # list task states
    items.append(urwid.Divider())
    items.append(urwid.Text('Task Icons:'))
    for state in TASK_STATUSES_ORDERED:
        items.append(
            urwid.Text(
                get_task_icon(state, colour='overlay')
                + [' ', state]
            )
        )
    items.append(urwid.Divider())
    items.append(urwid.Text('Special States:'))
    items.append(
        urwid.Text(
            get_task_icon(TASK_STATUS_WAITING, is_held=True, colour='overlay')
            + [' ', 'held']
        )
    )
    items.append(
        urwid.Text(
            get_task_icon(
                TASK_STATUS_WAITING,
                is_queued=True,
                colour='overlay',
            )
            + [' ', 'queued']
        )
    )
    items.append(
        urwid.Text(
            get_task_icon(
                TASK_STATUS_WAITING,
                is_runahead=True,
                colour='overlay',
            )
            + [' ', 'runahead']
        )
    )

    # list job states
    items.append(urwid.Divider())
    items.append(urwid.Text('Job Icons:'))
    for state in JOB_COLOURS:
        items.append(
            urwid.Text(
                [
                    (f'overlay_job_{state}', JOB_ICON),
                    ' ',
                    state
                ]
            )
        )

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker(items)
    )

    return (
        widget,
        {'width': 60, 'height': 40}
    )


def context(app):
    """An overlay for context menus."""
    value = app.tree_walker.get_focus()[0].get_node().get_value()
    selection = [value['id_']]  # single selection ATM

    is_running = True
    if (
        value['type_'] == 'workflow'
        and value['data']['status'] not in {'running', 'paused'}
    ):
        # this is a stopped workflow
        # => don't display mutations only valid for a running workflow
        is_running = False

    def _mutate(mutation, _):
        nonlocal app, selection

        app.open_overlay(partial(progress, text='Running Command'))
        overlay_fcn = None
        try:
            overlay_fcn = mutate(mutation, selection)
        except Exception as exc:
            app.open_overlay(partial(error, text=str(exc)))
        else:
            app.close_topmost()
            app.close_topmost()
        if overlay_fcn:
            app.open_overlay(overlay_fcn)

    # determine the ID to display for the context menu
    display_id = _get_display_id(value['id_'])
    header = [f'id: {display_id}']
    attrs = []

    # workflow state info
    if value['data'].get('status'):
        attrs.append(value['data']['status'])

    # task state info
    if value['data'].get('state'):
        attrs.append(
            value['data']['state']
            + (
                ' (held)' if value['data'].get('isHeld')
                else ' (queued)' if value['data'].get('isQueued')
                else '(runahead)' if value['data'].get('isRunahead')
                else ''
            )
        )

    # task flow info
    if value['data'].get('flowNums', '[1]') != '[1]':
        attrs.append(f'flows={format_flow_nums(value["data"]["flowNums"])}')

    if attrs:
        header.append(', '.join(attrs))

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker(
            [
                urwid.Text('\n'.join(header)),
                urwid.Divider(),
                urwid.Text('Action'),
                urwid.Button(
                    '(cancel)',
                    on_press=lambda *_: app.close_topmost()
                ),
                urwid.Divider()
            ] + [
                urwid.Button(
                    mutation,
                    on_press=partial(_mutate, mutation)
                )
                for mutation in list_mutations(
                    selection,
                    is_running,
                )
            ]
        )
    )

    return (
        widget,
        {'width': 50, 'height': 20}
    )


def error(app, text=''):
    """An overlay for unexpected errors."""
    return (
        urwid.ListBox([
            urwid.Text('Error'),
            urwid.Divider(),
            urwid.Text(text),
        ]),
        {'width': 50, 'height': 40}
    )


def progress(app, text='Working'):
    """An overlay for presenting a running action."""
    return (
        urwid.ListBox([
            urwid.Text(text),
        ]),
        {'width': 30, 'height': 10}
    )


def log(app, id_=None, list_files=None, get_log=None):
    """An overlay for displaying log files."""
    # display the host name where the file is coming from
    host_widget = urwid.Text('loading...')
    # display the log filepath
    file_widget = urwid.Text('')
    # display the actual log file itself
    text_widget = urwid.Text('')

    def open_menu(*_args, **_kwargs):
        """Open an overlay for selecting a log file."""
        nonlocal app, id_
        app.open_overlay(select_log)

    def select_log(*_args, **_kwargs):
        """Create an overlay for selecting a log file."""
        nonlocal list_files, id_
        try:
            files = list_files()
        except Exception as exc:
            return error(app, text=str(exc))
        return (
            urwid.ListBox([
                *[
                    urwid.Text('Select File'),
                    urwid.Divider(),
                ],
                *[
                    urwid.Button(
                        filename,
                        on_press=partial(
                            open_log,
                            filename=filename,
                            close=True,
                        ),
                    )
                    for filename in files
                ],
            ]),
            # NOTE: the "+6" avoids the need for scrolling
            {'width': 40, 'height': len(files) + 6}
        )

    def open_log(*_, filename=None, close=False):
        """View the provided log file.

        Args:
            filename:
                The name of the file to open (note name not path).
            close:
                If True, then the topmost overlay will be closed when a file is
                selected. Use this to close the "select_log" overlay.

        """

        nonlocal host_widget, file_widget, text_widget
        try:
            host, path, text = get_log(filename)
        except Exception as exc:
            host_widget.set_text(f'Error: {exc}')
            file_widget.set_text('')
            text_widget.set_text('')
        else:
            host_widget.set_text(f'Host: {host}')
            file_widget.set_text(f'Path: {path}')
            text_widget.set_text(text)
            if close:
                app.close_topmost()

    # load the default log file
    if id_:
        # NOTE: the kwargs are not provided in the overlay unit tests
        open_log()

    return (
        ListBoxPlus([
            # NOTE: We use a ListBox here because it allows the file-select
            # button to have focus whilst keeping the overlay scrollable at the
            # same time.
            host_widget,
            file_widget,
            urwid.Button(
                'Select File',
                on_press=open_menu,
            ),
            urwid.Divider(),
            text_widget,
        ]),
        # open full screen
        {'width': 9999, 'height': 9999}
    )


def text_box(app, text=''):
    """A simple text box overlay."""
    width, height = get_text_dimensions(text)
    return (
        urwid.ListBox([
            urwid.Text(text),
        ]),
        # NOTE: those fudge factors account for the overlay border & padding
        {'width': width + 4, 'height': height + 6}
    )
