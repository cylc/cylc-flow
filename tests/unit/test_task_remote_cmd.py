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
"""Tests for remote initialisation."""

from unittest.mock import patch

from cylc.flow.task_remote_cmd import remote_init


@patch('os.makedirs')
@patch('os.listdir')
@patch('os.path.join')
@patch('os.path.expandvars')
def test_existing_key_raises_error(
        mocked_expandvars, mocked_pathjoin, mocked_listdir,
        mocked_makedirs, capsys):
    """Test .service directory that contains existing incorrect key,
       results in REMOTE INIT FAILED
    """
    mocked_expandvars.return_value = "some/expanded/path"
    mocked_pathjoin.return_value = "joined.path"
    mocked_listdir.return_value = ['client_wrong.key']

    remote_init('test_install_target', 'some_rund')
    assert capsys.readouterr().out == "REMOTE INIT FAILED\n"


@patch('os.path.expandvars')
def test_unexpandable_symlink_env_var_returns_failed(
        mocked_expandvars, capsys):
    """Test unexpandable symlinks return REMOTE INIT FAILED"""
    mocked_expandvars.side_effect = ['some/rund/path', '$blah']

    remote_init('test_install_target', 'some_rund', 'run=$blah')
    assert capsys.readouterr().out == "REMOTE INIT FAILED\n"
