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
"""Overlay panels for Tui.

Panels are functions::

    function(app) -> (widget, overlay_options)

Parameters:

    app:
        Tui application object.
    widget (urwid.Widget):
        A widget to place in the overlay.
    overlay_optios (dict):
        A dictionary of keyword argumnts to provide to the
        urwid.Overlay constructor.

        You will likely want to override the `width` and `height`
        arguments.

        See the `urwid` documentation for details.

"""

from functools import partial

import urwid

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
            get_task_icon(state, False)
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
            urwid.Button(
                'Invert',
                on_press=invert
            )
        ] + checkboxes + [
            urwid.Divider(),
            urwid.Text('"q" to close')
        ])
    )

    return (
        widget,
        {'width': 35, 'height': 23}
    )
