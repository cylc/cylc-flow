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

"""Shared utilities for Cylc scripts."""

from itertools import zip_longest
from ansimarkup import strip

from cylc.flow import __version__
from cylc.flow.scripts import _copyright_year
from cylc.flow.terminal import get_width

# fmt: off
CYLC_LOGO = [
    " <yellow>▪</yellow> <blue>■ </blue>",
    " <green>██</green>  ",
    "<red>▝▘</red>   ",
]
# fmt: on

CYLC = (
    "<b>"
    "<red>C</red>"
    "<yellow>y</yellow>"
    "<green>l</green>"
    "<blue>c</blue>"
    "</b>"
)

VERSION = f"<b><yellow>{__version__}</yellow></b>"

LICENSE = [
    f"{CYLC} Workflow Engine {VERSION}",
    f"Copyright (C) 2008-{_copyright_year} NIWA",
    "& British Crown (Met Office) & Contributors"
]


def cylc_header(width=None):
    """Print copyright and license information."""
    width = width or get_width()
    lmax = (
        max(len(strip(line)) for line in LICENSE) +
        len(strip(CYLC_LOGO[0]))
    )
    if width >= lmax + 1:
        header = '\n'.join(
            ('{0} {1}').format(*x)
            for x in zip_longest(
                CYLC_LOGO,
                LICENSE
            )
        )
    else:
        header = '\n'.join(CYLC_LOGO) + '\n' + '\n'.join(LICENSE)
    return f"\n{header}\n"
