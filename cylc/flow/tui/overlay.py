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
import sys

import urwid

from cylc.flow.exceptions import (
    ClientError,
)
from cylc.flow.task_state import (
    TASK_STATUSES_ORDERED,
    TASK_STATUS_WAITING
)
from cylc.flow.tui import (
    BINDINGS,
    JOB_COLOURS,
    JOB_ICON,
    TUI
)
from cylc.flow.tui.data import (
    list_mutations,
    mutate,
)
from cylc.flow.tui.util import (
    get_task_icon
)


def filter_task_state(app):
    """Return a widget for adjusting the task state filter."""

    def toggle(state, *_):
        """Toggle a filter state."""
        app.filter_states[state] = not app.filter_states[state]

    checkboxes = [
        urwid.CheckBox(
            get_task_icon(state)
            + [' ' + state],
            state=is_on,
            on_state_change=partial(toggle, state)
        )
        for state, is_on in app.filter_states.items()
    ]

    def invert(*_):
        """Invert the state of all filters."""
        for checkbox in checkboxes:
            checkbox.set_state(not checkbox.state)

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker([
            urwid.Text('Filter Task States'),
            urwid.Divider(),
            urwid.Padding(
                urwid.Button(
                    'Invert',
                    on_press=invert
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
    for group, bindings in BINDINGS.list_groups():
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

    def _mutate(mutation, _):
        nonlocal app
        app.open_overlay(partial(progress, text='Running Command'))
        try:
            mutate(app.client, mutation, selection)
        except ClientError as exc:
            app.open_overlay(partial(error, text=str(exc)))
        else:
            app.close_topmost()
            app.close_topmost()

    widget = urwid.ListBox(
        urwid.SimpleFocusListWalker(
            [
                urwid.Text(f'id: {value["id_"]}'),
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
                for mutation in list_mutations(app.client, selection)
            ]
        )
    )

    return (
        widget,
        {'width': 30, 'height': 20}
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
