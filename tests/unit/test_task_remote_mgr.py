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

import pytest
from typing import Any
from unittest.mock import MagicMock, Mock

from cylc.flow.task_remote_mgr import (
    REMOTE_FILE_INSTALL_DONE, REMOTE_INIT_IN_PROGRESS, TaskRemoteMgr)

Fixture = Any


@pytest.mark.parametrize(
    'install_target, skip_expected, expected_status',
    [('localhost', True, REMOTE_FILE_INSTALL_DONE),
     ('something_else', False, REMOTE_INIT_IN_PROGRESS)]
)
def test_remote_init_skip(
        install_target: str, skip_expected: bool, expected_status: str,
        monkeypatch: Fixture):
    """Test the TaskRemoteMgr.remote_init() skips localhost install target.

    Params:
        install_target: The platform's install target.
        skip_expected: Whether remote init is expected to be skipped.
        expected_status: The expected value of
            TaskRemoteMgr.remote_init_map[install_target].
    """
    platform = {
        'install target': install_target,
        'communication method': 'whatever'
    }
    mock_task_remote_mgr = MagicMock(remote_init_map={})
    mock_construct_ssh_cmd = Mock()
    monkeypatch.setattr('cylc.flow.task_remote_mgr.construct_ssh_cmd',
                        mock_construct_ssh_cmd)
    for item in ('tarfile', 'get_remote_suite_run_dir', 'get_dirs_to_symlink'):
        monkeypatch.setattr(f'cylc.flow.task_remote_mgr.{item}', MagicMock())

    TaskRemoteMgr.remote_init(mock_task_remote_mgr, platform, None, None)
    call_expected = not skip_expected
    assert mock_task_remote_mgr._remote_init_items.called is call_expected
    assert mock_construct_ssh_cmd.called is call_expected
    assert mock_task_remote_mgr.proc_pool.put_command.called is call_expected
    status = mock_task_remote_mgr.remote_init_map[install_target]
    assert status == expected_status
