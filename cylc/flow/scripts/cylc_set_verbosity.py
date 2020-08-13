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

"""cylc [control] set-verbosity [OPTIONS] ARGS

Change the logging severity level of a running suite.  Only messages at
or above the chosen severity level will be logged; for example, if you
choose WARNING, only warnings and critical messages will be logged."""

from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.terminal import prompt, cli_function

LOGGING_LVL_OF = {
    "INFO": INFO,
    "NORMAL": INFO,
    "WARNING": WARNING,
    "ERROR": ERROR,
    "CRITICAL": CRITICAL,
    "DEBUG": DEBUG,
}


def get_option_parser():
    parser = COP(
        __doc__, comms=True,
        argdoc=[
            ('REG', 'Suite name'),
            ('LEVEL', ', '.join(LOGGING_LVL_OF.keys()))
        ]
    )

    return parser


@cli_function(get_option_parser)
def main(parser, options, suite, severity_str):
    try:
        severity = LOGGING_LVL_OF[severity_str]
    except KeyError:
        parser.error("Illegal logging level, %s" % severity_str)

    prompt("Set logging level to %s in %s" % (severity_str, suite),
           options.force)
    pclient = SuiteRuntimeClient(suite, timeout=options.comms_timeout)
    pclient('set_verbosity', {'level': severity})


if __name__ == "__main__":
    main()
