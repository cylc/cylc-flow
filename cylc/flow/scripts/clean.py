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

"""cylc clean [OPTIONS] ARGS

Remove a stopped workflow from the local scheduler filesystem and remote hosts.

NOTE: this command is intended for workflows installed with `cylc install`. If
this is run for a workflow that was instead written directly in ~/cylc-run and
not backed up elsewhere, it will be lost.

It will also remove any symlink directory targets.

Workflow names can be hierarchical, corresponding to the path under ~/cylc-run.

Examples:
  # Remove the workflow at ~/cylc-run/foo/bar
  $ cylc clean foo/bar

  # Remove the workflow's log directory
  $ cylc clean foo/bar --rm log

  # Remove the log and work directories
  $ cylc clean foo/bar --rm log:work
  # or
  $ cylc clean foo/bar --rm log --rm work

  # Remove all job log files from the 2020 cycle points
  cylc clean foo/bar --rm 'log/job/2020*'

  # Remove all .csv files
  $ cylc clean foo/bar --rm '**/*.csv'

  # Only remove the workflow on the local filesystem
  $ cylc clean foo/bar --local-only

  # Only remove the workflow on remote install targets
  $ cylc clean foo/bar --remote-only

"""

from typing import TYPE_CHECKING

import cylc.flow.flags
from cylc.flow import LOG
from cylc.flow.exceptions import UserInputError
from cylc.flow.loggingutil import CylcLogFormatter
from cylc.flow.option_parsers import CylcOptionParser as COP, Options
from cylc.flow.terminal import cli_function
from cylc.flow.workflow_files import init_clean

if TYPE_CHECKING:
    from optparse import Values


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[('REG', "Workflow name")]
    )

    parser.add_option(
        '--rm', metavar='DIR[:DIR:...]',
        help="Only clean the specified subdirectories (or files) in the "
             "run directory, rather than the whole run directory. "
             "Accepts quoted globs.",
        action='append', dest='rm_dirs', default=[]
    )

    parser.add_option(
        '--local-only', '--local',
        help="Only clean on the local filesystem (not remote hosts).",
        action='store_true', dest='local_only'
    )

    parser.add_option(
        '--remote-only', '--remote',
        help="Only clean on remote hosts (not the local filesystem).",
        action='store_true', dest='remote_only'
    )

    parser.add_option(
        '--timeout',
        help="The number of seconds to wait for cleaning to take place on "
             "remote hosts before cancelling.",
        action='store', default='120', dest='remote_timeout'
    )

    return parser


CleanOptions = Options(get_option_parser())


@cli_function(get_option_parser)
def main(parser: COP, opts: 'Values', reg: str):
    if cylc.flow.flags.verbosity < 2:
        # for readability omit timestamps from logging unless in debug mode
        for handler in LOG.handlers:
            if isinstance(handler.formatter, CylcLogFormatter):
                handler.formatter.configure(timestamp=False)

    if opts.local_only and opts.remote_only:
        raise UserInputError(
            "--local and --remote options are mutually exclusive"
        )

    init_clean(reg, opts)


if __name__ == "__main__":
    main()
