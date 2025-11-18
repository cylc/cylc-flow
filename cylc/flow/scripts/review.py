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
"""cylc review [start|stop]

Start/stop ad-hoc Cylc Review web service server for browsing users' suite
logs via an HTTP interface.

With no arguments, the status of the ad-hoc web service server is printed.
"""

import os
import signal

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.review import CylcReviewService
from cylc.flow.terminal import cli_function
from cylc.flow.ws import _ws_init, _get_server_status


IRRELEVANT_OPTS = [
    '--host',
    '--user',
    '--verbose',
    '--debug',
    '--quiet',
    '--timestamp',
    '--no-timestamp',
    '--color',
]
START = 'start'
STOP = 'stop'


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            COP.optional(("start", "Start ad-hoc web service server.")),
            COP.optional(("stop", "Stop ad-hoc web service server.")),
        ],
    )

    parser.add_option(
        '--port',
        '-p',
        help="Port to use for Cylc Review (for start only).",
        default=8080,
        action='store',
        type=int,
    )
    parser.add_option(
        "--non-interactive",
        "--yes",
        "-y",
        help="Switch off interactive prompting i.e. answer yes to everything"
        " (for stop only).",
        action="store_true",
        default=False,
        dest="non_interactive",
    )
    parser.add_option(
        "--service-root",
        "-R",
        help="Include web service name under root of URL (for start only).",
        action="store",
        default='/',
        dest="service_root",
    )
    return parser


@cli_function(get_option_parser, remove_opts=IRRELEVANT_OPTS)
def main(_, opts, *args):
    """Start/Stop the Cylc Review server."""
    subcmd = args[0] if args else ''

    # Get current server status:
    status = _get_server_status(CylcReviewService)

    # User has asked to start the server, and it's not already running:
    if subcmd == START:
        _ws_init(
            service_cls=CylcReviewService,
            port=opts.port,
            service_root=opts.service_root,
        )
    # User has asked to stop or get info on server, server _not_ running:
    elif not status:
        print(f'No {CylcReviewService.TITLE} service server running.')
    else:
        # Report on status of server:
        for key, value in sorted(status.items()):
            print(f'{key}={value}')

        # User has asked to stop the server:
        if (
            subcmd == STOP  # User asked for server stop
            and status.get('pid')  # Server is running
            and (  # User really wants to stop the server
                opts.non_interactive
                or input("Stop server by termination? y/n(default=n)") == "y"
            )
        ):
            try:
                os.killpg(int(status["pid"]), signal.SIGTERM)
            except OSError:
                print("Termination signal failed.")
