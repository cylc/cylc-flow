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
"""cylc [task] remote-tidy RUND

(This command is for internal use.)

Remove ".service/contact" from a task remote (i.e. a [owner@]host).
Remove ".service" directory on the remote if emptied.
Remove authentication keys.

"""

from cylc.flow.option_parsers import CylcOptionParser as COP
from cylc.flow.task_remote_cmd import remote_tidy

INTERNAL = True


def main():
    parser = COP(
        __doc__, argdoc=[("INSTALL_TARGET", "target platform to be tidied"),
                         ("RUND", "The run directory of the suite")]
    )
    options, (install_target, rund) = parser.parse_args()
    remote_tidy(install_target, rund)


if __name__ == "__main__":
    main()
