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

from textwrap import dedent

from ansimarkup import parse as cparse
import pytest

from cylc.flow.scripts.reinstall import format_reinstall_output
from cylc.flow.terminal import DIM


@pytest.mark.parametrize('verbose', [True, False])
def test_format_reinstall_output(verbose, monkeypatch: pytest.MonkeyPatch):
    """It should:
    - colorize the output
    - remove the itemized changes summary if not in verbose mode
    - remove the "cannot delete non-empty directory" message
    """
    output = dedent("""
        *deleting   del. Cloud.jpg
        >f+++++++++ send cloud.jpg
        .f...p..... send foo
        >fcsTp..... send bar
        cannot delete non-empty directory: scarf
        >f+++++++++ send meow.txt
        cL+++++++++ send garage -> foo
    """).strip()
    expected = [
        f"<{DIM}>*deleting  </{DIM}> <red>del. Cloud.jpg</red>",
        f"<{DIM}>>f+++++++++</{DIM}> <green>send cloud.jpg</green>",
        f"<{DIM}>.f...p.....</{DIM}> <green>send foo</green>",
        f"<{DIM}>>fcsTp.....</{DIM}> <green>send bar</green>",
        f"<{DIM}>>f+++++++++</{DIM}> <green>send meow.txt</green>",
        f"<{DIM}>cL+++++++++</{DIM}> <green>send garage -> foo</green>",
    ]
    if verbose:
        monkeypatch.setattr('cylc.flow.flags.verbosity', 1)
    else:
        # itemized changes summary should not be in output
        shift = len(f'<{DIM}></{DIM}> ') + 11
        expected = [i[shift:] for i in expected]
    assert format_reinstall_output(output) == [cparse(i) for i in expected]
