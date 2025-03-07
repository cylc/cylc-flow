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
from cylc.flow.scripts.reinstall import format_rsync_out


def test_format_rsync_out():
    """It should:
    - colorize the output
    - remove the itemized changes from rsync format
    - remove the "cannot delete non-empty directory" message
    """
    rsync_output = dedent("""
        del. *deleting   Cloud.jpg
        send >f+++++++++ cloud.jpg
        send .f...p..... foo
        send >fcsTp..... bar
        cannot delete non-empty directory: opt
        send >f+++++++++ meow.txt
        send cL+++++++++ garage -> foo
    """).strip()
    assert format_rsync_out(rsync_output) == [
        cparse("<red>del.</red> Cloud.jpg"),
        cparse("<green>send</green> cloud.jpg"),
        cparse("<green>send</green> foo"),
        cparse("<green>send</green> bar"),
        cparse("<green>send</green> meow.txt"),
        cparse("<green>send</green> garage -> foo"),
    ]
