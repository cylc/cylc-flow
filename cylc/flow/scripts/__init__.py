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

from itertools import zip_longest
from textwrap import dedent
import re
from ansimarkup import strip

from cylc.flow import __version__
from cylc.flow.terminal import get_width


_copyright_year = 2021  # This is set by GH Actions update_copyright workflow

# fmt: off
LOGO_LETTERS = (
    (
        "oooo",
        "oo  ",
        "oooo",
    ),
    (
        "oo oo",
        "ooooo",
        "   oo",
    ),
    (
        "oo",
        "oo",
        "oo",
    ),
    (
        "oooo",
        "oo  ",
        "oooo",
    )
)
# fmt: on

LOGO_LINES = [
    ''.join(
        re.sub('o', f'<white,{tag}> </white,{tag}>', letter[ind])
        for tag, letter in zip(
            ('red', 'yellow', 'green', 'blue'),
            LOGO_LETTERS
        )
    )
    for ind in range(len(LOGO_LETTERS[0]))
]

LICENSE = dedent(f"""
    The Cylc Workflow Engine [{__version__}]
    Copyright (C) 2008-{_copyright_year} NIWA &
    British Crown (Met Office) & Contributors
""")

CYLC = (
    "<b>"
    "<red>C</red>"
    "<yellow>y</yellow>"
    "<green>l</green>"
    "<blue>c</blue>"
    "</b>"
)


def cylc_header(width=None):
    """Print copyright and license information."""
    if not width:
        width = get_width()
    # center license lines
    llines = LICENSE.strip().splitlines()
    lmax = max(len(line) for line in llines)
    llines = [
        line.center(lmax)
        for line in llines
        if line
    ]
    llines[0] = re.sub('Cylc', CYLC, llines[0])
    tlmax = lmax + len(strip(LOGO_LINES[0]))
    lpad = int((width - tlmax) / 2) * ' '
    return '\n' + lpad + f'\n{lpad}'.join(
        ('{0}  {1}').format(*x)
        for x in zip_longest(
            LOGO_LINES,
            llines
        )
    )
