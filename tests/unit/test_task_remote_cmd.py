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

from pathlib import Path
from unittest.mock import patch
from pytest import CaptureFixture

from cylc.flow.suite_files import SuiteFiles
from cylc.flow.task_remote_cmd import remote_init


def test_existing_key_raises_error(tmp_path: Path, capsys: CaptureFixture):
    """Test .service directory that contains existing incorrect key,
    results in REMOTE INIT FAILED"""
    rundir = tmp_path / 'some_rund'
    srvdir = rundir / SuiteFiles.Service.DIRNAME
    srvdir.mkdir(parents=True)
    (srvdir / 'client_wrong.key').touch()

    remote_init('test_install_target', str(rundir))
    assert capsys.readouterr().out == (
        "REMOTE INIT FAILED\nUnexpected authentication key"
        " \"client_wrong.key\" exists. Check global.cylc install target is"
        " configured correctly for this platform.\n")


@patch('os.path.expandvars')
def test_unexpandable_symlink_env_var_returns_failed(
        mocked_expandvars, capsys):
    """Test unexpandable symlinks return REMOTE INIT FAILED"""
    mocked_expandvars.side_effect = ['some/rund/path', '$blah']

    remote_init('test_install_target', 'some_rund', 'run=$blah')
    assert capsys.readouterr().out == (
        "REMOTE INIT FAILED\nError occurred when symlinking."
        " $blah contains an invalid environment variable.\n")


def test_existing_client_key_dir_raises_error(
        tmp_path: Path, capsys: CaptureFixture):
    """Test .service directory that contains existing incorrect key,
       results in REMOTE INIT FAILED
    """
    rundir = tmp_path / 'some_rund'
    keydir = rundir / SuiteFiles.Service.DIRNAME / "client_public_keys"
    keydir.mkdir(parents=True)

    remote_init('test_install_target', rundir)
    assert capsys.readouterr().out == (
        f"REMOTE INIT FAILED\nUnexpected key directory exists: {keydir}"
        " Check global.cylc install target is configured correctly for this"
        " platform.\n")
