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

from contextlib import suppress
from functools import partial
import re
import sys

import urwid

from cylc.flow.exceptions import (
    ClientError,
    ClientTimeout,
    WorkflowStopped,
)
from cylc.flow.id import Tokens
from cylc.flow.network.client_factory import get_client
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
    extract_context,
    list_mutations,
    mutate,
)
from cylc.flow.tui.util import (
    get_task_icon,
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
            get_task_icon(state)
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
                get_task_icon(state)
                + [' ', state]
            )
        )
    items.append(urwid.Divider())
    items.append(urwid.Text('Special States:'))
    items.append(
        urwid.Text(
            get_task_icon(TASK_STATUS_WAITING, is_held=True)
            + [' ', 'held']
        )
    )
    items.append(
        urwid.Text(
            get_task_icon(TASK_STATUS_WAITING, is_queued=True)
            + [' ', 'queued']
        )
    )
    items.append(
        urwid.Text(
            get_task_icon(TASK_STATUS_WAITING, is_runahead=True)
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
    context = extract_context(selection)

    client = None
    if 'workflow' in context:
        w_id = context['workflow'][0]
        with suppress(WorkflowStopped, ClientError, ClientTimeout):
            client = get_client(w_id)

    def _mutate(mutation, _):
        nonlocal app, client
        app.open_overlay(partial(progress, text='Running Command'))
        try:
            mutate(client, mutation, selection)
        except ClientError as exc:
            app.open_overlay(partial(error, text=str(exc)))
        else:
            app.close_topmost()
            app.close_topmost()

    # determine the ID to display for the context menu
    display_id = _get_display_id(value['id_'])

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker(
            [
                urwid.Text(f'id: {display_id}'),
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
                for mutation in list_mutations(client, selection)
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
