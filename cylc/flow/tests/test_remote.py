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
"""Test the cylc.flow.remote module."""

from subprocess import PIPE

from cylc.flow.remote import run_cmd


def test_run_cmd_stdin_str():
    """Test passing stdin as a string."""
    proc = run_cmd(
        ['sed', 's/foo/bar/'],
        stdin_str='1foo2',
        capture_process=True
    )
    assert proc.communicate() == (
        b'1bar2',
        b''
    )


def test_run_cmd_stdin_file(tmp_path):
    """Test passing stdin as a file."""
    tmp_path = tmp_path / 'stdin'
    with tmp_path.open('w+') as tmp_file:
        tmp_file.write('1foo2')
    tmp_file = tmp_path.open('rb')
    proc = run_cmd(
        ['sed', 's/foo/bar/'],
        stdin=tmp_file,
        capture_process=True
    )
    assert proc.communicate() == (
        b'1bar2',
        b''
    )
