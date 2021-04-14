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

"""cylc clean [OPTIONS] ARGS

Remove a stopped workflow from the local scheduler filesystem and remote hosts.

NOTE: this command is intended for workflows installed with `cylc install`. If
this is run for a workflow that was instead written directly in ~/cylc-run and
not backed up elsewhere, it will be lost.

It will also remove any symlink directory targets.

Suite names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Remove the workflow at ~/cylc-run/foo/bar
  $ cylc clean foo/bar

"""

import cylc.flow.flags
from cylc.flow import LOG
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.terminal import cli_function
from cylc.flow.suite_files import clean, init_clean

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[('REG', "Workflow name")]
    )

    parser.add_option(
        '--local-only', '--local',
        help="Only clean on the local filesystem (not remote hosts).",
        action='store_true', dest='local_only'
    )

    parser.add_option(
        '--timeout',
        help="The number of seconds to wait for cleaning to take place on "
             "remote hosts before cancelling.",
        action='store', default='120', dest='remote_timeout'
    )

    return parser


@cli_function(get_option_parser)
def main(parser: COP, opts: 'Values', reg: str):
    if not cylc.flow.flags.debug:
        # for readability omit timestamps from logging unless in debug mode
        for handler in LOG.handlers:
            if isinstance(handler.formatter, CylcLogFormatter):
                handler.formatter.configure(timestamp=False)

    if opts.local_only:
        clean(reg)
    else:
        init_clean(reg, opts)


if __name__ == "__main__":
    main()
