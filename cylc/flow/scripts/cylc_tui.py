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
"""cylc [task] tui REG

Open the terminal user interface (TUI) for the given suite.
"""
from textwrap import indent

from urwid import html_fragment

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.tui import (
    TUI
)
from cylc.flow.tui.app import (
    TuiApp,
    TREE_EXPAND_DEPTH
    # ^ a nasty solution
)


__doc__ += indent(TUI, '           ')


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
        screen.register_palette(TuiApp.palette)
        html_fragment.screenshot_init(
            [tuple(map(int, options.v_term_size.split(',')))],
            []
        )

    try:
        TuiApp(reg, screen=screen).main()

        if options.display == 'html':
            for fragment in html_fragment.screenshot_collect():
                print(fragment)
    except KeyboardInterrupt:
        pass
