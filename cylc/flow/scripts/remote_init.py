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
"""cylc remote-init [--indirect-comm=ssh] INSTALL_TARGET RUND

(This command is for internal use.)

Install suite service files on a task remote (i.e. a [owner@]host):
    .service/contact: All task -> suite communication methods.

Content of items to install from a tar file read from STDIN.

Return:
    0:
        On success or if initialisation not required:
        - Print task_remote_cmd.REMOTE_INIT_NOT_REQUIRED if initialisation
          not required (e.g. remote has shared file system with suite host).
        - Print task_remote_cmd.REMOTE_INIT_DONE on success.
    1:
        On failure.

"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_remote_cmd import remote_init
from cylc.flow.terminal import cli_function

INTERNAL = True


def get_option_parser():
    parser = COP(
        __doc__,
        argdoc=[
            ("INSTALL_TARGET", "Target to be initialised"),
            ("RUND", "The run directory of the suite"),
            ('[DIRS_TO_BE_SYMLINKED ...]', "Directories to be symlinked"),
        ],
        color=False
    )
    parser.add_option(
        "--indirect-comm",
        metavar="METHOD",
        type="choice",
        choices=["ssh"],
        help="specify use of indirect communication via e.g. ssh",
        action="store",
        dest="indirect_comm",
        default=None,
    )

    return parser


@cli_function(get_option_parser)
def main(parser, options, install_target, rund, *dirs_to_be_symlinked):

    remote_init(
        install_target,
        rund,
        *dirs_to_be_symlinked,
        indirect_comm=options.indirect_comm)


if __name__ == "__main__":
    main()
