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

from pathlib import Path
from time import sleep
import pytest
from typing import (Any, Optional)
from unittest.mock import MagicMock, Mock

from cylc.flow.network.client_factory import CommsMeth
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
        'communication method': CommsMeth.POLL,
        'hosts': ['localhost'],
        'selection': {'method': 'random'},
        'name': 'foo'
    }
    mock_task_remote_mgr = MagicMock(remote_init_map={}, bad_hosts=[])
    mock_construct_ssh_cmd = Mock()
    monkeypatch.setattr('cylc.flow.task_remote_mgr.construct_ssh_cmd',
                        mock_construct_ssh_cmd)
    for item in (
            'tarfile',
            'get_remote_workflow_run_dir',
            'get_dirs_to_symlink'):
        monkeypatch.setattr(f'cylc.flow.task_remote_mgr.{item}', MagicMock())

    TaskRemoteMgr.remote_init(mock_task_remote_mgr, platform, None, '')
    call_expected = not skip_expected
    assert mock_task_remote_mgr._remote_init_items.called is call_expected
    assert mock_construct_ssh_cmd.called is call_expected
    assert mock_task_remote_mgr.proc_pool.put_command.called is call_expected
    status = mock_task_remote_mgr.remote_init_map[install_target]
    assert status == expected_status


@pytest.mark.parametrize(
    'install_target, load_type, expected',
    [
        ('install_target', None, '03-start-install_target.log'),
        ('some_install_target',
         'restart',
         '03-restart-some_install_target.log'),
        ('another_install_target',
         'reload',
         '03-reload-another_install_target.log')
    ]
)
def test_get_log_file_name(tmp_path,
                           install_target: str,
                           load_type: Optional[str],
                           expected: str):
    task_remote_mgr = TaskRemoteMgr('some_workflow', None, None)
    if load_type == 'restart':
        task_remote_mgr.is_restart = True
    elif load_type == 'reload':
        task_remote_mgr.is_reload = True
    # else load type is start (no flag required)
    run_dir = tmp_path
    log_dir = Path(run_dir/'some_workflow'/'log'/'remote-install')
    log_dir.mkdir(parents=True)
    for log_num in range(1, 3):
        Path(f"{log_dir}/{log_num:02d}-start-{install_target}.log").touch()
        sleep(0.1)
    log_name = task_remote_mgr.get_log_file_name(
        install_target, install_log_dir=log_dir)
    assert log_name == expected
