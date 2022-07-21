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
"""cylc remote-init [OPTIONS] ARGS

(This command is for internal use.)

Initialise an install target.

Initialisation creates a workflow run directory on the install target,
"$HOME/cylc-run/<WORKFLOW_NAME>/". The .service directory is also created and
populated with the install target authentication files and the contact file.

Symlinks are created for run, work, share, share/cycle, log directories,
configured in the global.flow.

Return:
    0:
        On success or if initialisation not required:
        - Print task_remote_cmd.REMOTE_INIT_DONE
    1:
        On failure.
"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_remote_cmd import remote_init
from cylc.flow.terminal import cli_function

INTERNAL = True


def get_option_parser() -> COP:
    parser = COP(
        __doc__,
        argdoc=[
            ("INSTALL_TARGET", "Target to be initialised"),
            ("RUND", "The run directory of the workflow"),
            COP.optional(
                ('DIRS_TO_BE_SYMLINKED ...', "Directories to be symlinked")
            )
        ],
        color=False
    )

    return parser


@cli_function(get_option_parser)
def main(parser, options, install_target, rund, *dirs_to_be_symlinked):

    remote_init(
        install_target,
        rund,
        *dirs_to_be_symlinked
    )
