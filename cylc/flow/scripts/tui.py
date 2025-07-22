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

"""cylc tui [WORKFLOW]

View and control running workflows in the terminal.

(Tui = Terminal User Interface)

Tui allows you to monitor and interact with workflows in a manner similar
to the GUI.

Press "h" whilst running Tui to bring up the help screen, use the arrow
keys to navigate.

"""

from getpass import getuser
from textwrap import indent
from typing import TYPE_CHECKING, Optional

from cylc.flow.id import Tokens
from cylc.flow.id_cli import parse_id
from cylc.flow.option_parsers import (
    OPT_WORKFLOW_ID_ARG_DOC,
    CylcOptionParser as COP,
)
from cylc.flow.terminal import cli_function
from cylc.flow.tui import TUI
from cylc.flow.tui.util import suppress_logging
from cylc.flow.tui.app import (
    TuiApp,
)

if TYPE_CHECKING:
    from optparse import Values


__doc__ += indent(TUI, '           ')


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[OPT_WORKFLOW_ID_ARG_DOC],
        # auto_add=False,  NOTE: at present auto_add can not be turned off
        color=False
    )

    parser.add_option(
        '--comms-timeout',
        metavar='SEC',
        help=(
            # NOTE: Tui overrides the default client timeout
            "Set the timeout for communication with the running workflow."
            " The default is 5 seconds, you may need to increase this in"
            " order for Tui to keep up with especially busy workflows."
        ),
        action='store',
        default=5,
        dest='comms_timeout',
        type=int,
    )

    return parser


@cli_function(get_option_parser)
def main(_, options: 'Values', workflow_id: Optional[str] = None) -> None:
    # get workflow ID if specified
    if workflow_id:
        workflow_id, *_ = parse_id(
            workflow_id,
            constraint='workflows',
        )
        tokens = Tokens(workflow_id)
        workflow_id = tokens.duplicate(user=getuser()).id

    # start Tui
    with suppress_logging(), TuiApp().main(
        workflow_id,
        client_timeout=options.comms_timeout,
    ):
        # tui stops according to user input
        pass
