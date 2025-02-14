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

from contextlib import suppress
from pathlib import Path
from time import sleep
import pytest
from typing import (Any, Optional)
from unittest.mock import MagicMock, Mock

from cylc.flow.exceptions import PlatformError
from cylc.flow.network.client_factory import CommsMeth
from cylc.flow.task_remote_mgr import (
    REMOTE_FILE_INSTALL_DONE, REMOTE_INIT_IN_PROGRESS, TaskRemoteMgr)
from cylc.flow.workflow_files import WorkflowFiles, get_workflow_srv_dir


Fixture = Any


@pytest.mark.parametrize(
    'comms_meth, expected',
    [
        (CommsMeth.SSH, True),
        (CommsMeth.ZMQ, True),
        (CommsMeth.POLL, False)
    ]
)
def test__remote_init_items(comms_meth: CommsMeth, expected: bool):
    """Test _remote_init_items().

    Should only includes files under .service/
    """
    id_ = 'barclay'
    mock_mgr = Mock(workflow=id_)
    srv_dir = get_workflow_srv_dir(id_)
    items = TaskRemoteMgr._remote_init_items(mock_mgr, comms_meth)
    if expected:
        assert items
        for src_path, dst_path in items:
            Path(src_path).relative_to(srv_dir)
            Path(dst_path).relative_to(WorkflowFiles.Service.DIRNAME)
    else:
        assert not items


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

    TaskRemoteMgr.remote_init(mock_task_remote_mgr, platform)
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
def test_get_log_file_name(tmp_path: Path,
                           install_target: str,
                           load_type: Optional[str],
                           expected: str):
    task_remote_mgr = TaskRemoteMgr('some_workflow', None, None, None, None)
    if load_type == 'restart':
        task_remote_mgr.is_restart = True
    elif load_type == 'reload':
        task_remote_mgr.is_reload = True
    # else load type is start (no flag required)
    run_dir = tmp_path
    log_dir = run_dir / 'some_workflow' / 'log' / 'remote-install'
    log_dir.mkdir(parents=True)
    for log_num in range(1, 3):
        Path(f"{log_dir}/{log_num:02d}-start-{install_target}.log").touch()
        sleep(0.1)
    log_name = task_remote_mgr.get_log_file_name(
        install_target, install_log_dir=log_dir)
    assert log_name == expected


@pytest.mark.parametrize(
    'platform_names, install_targets, glblcfg, expect',
    [
        pytest.param(
            # Two platforms share an install target. Both are reachable.
            ['sir_handel', 'peter_sam'],
            ['mountain_railway'],
            '''
            [platforms]
                [[peter_sam, sir_handel]]
                    install target = mountain_railway
            ''',
            {
                'targets': {'mountain_railway': ['peter_sam', 'sir_handel']},
                'unreachable': set()
            },
            id='basic'
        ),
        pytest.param(
            # Two platforms share an install target. Both are unreachable.
            set(),
            ['mountain_railway'],
            '''
            [platforms]
                [[peter_sam, sir_handel]]
                    install target = mountain_railway
            ''',
            {
                'targets': {'mountain_railway': []},
                'unreachable': {'mountain_railway'}
            },
            id='platform_unreachable'
        ),
        pytest.param(
            # One of our install targets matches one of our platforms,
            # but only implicitly; i.e. the platform name is the same as the
            # install target name.
            ['sir_handel'],
            ['sir_handel'],
            '''
            [platforms]
                [[sir_handel]]
            ''',
            {
                'targets': {'sir_handel': ['sir_handel']},
                'unreachable': set()
            },
            id='implicit-target'
        ),
        pytest.param(
            # One of our install targets matches one of our platforms,
            # but only implicitly, and the platform name is defined using a
            # regex.
            ['sir_handel42'],
            ['sir_handel42'],
            '''
            [platforms]
                [[sir_handel..]]
            ''',
            {
                'targets': {'sir_handel42': ['sir_handel42']},
                'unreachable': set()
            },
            id='implicit-target-regex'
        ),
        pytest.param(
            # One of our install targets (rusty) has no defined platforms
            # causing a PlatformLookupError.
            ['duncan', 'rusty'],
            ['mountain_railway', 'rusty'],
            '''
            [platforms]
                [[duncan]]
                    install target = mountain_railway
            ''',
            {
                'targets': {'mountain_railway': ['duncan']},
                'unreachable': {'rusty'}
            },
            id='PlatformLookupError'
        )
    ]
)
def test_map_platforms_used_for_install_targets(
    mock_glbl_cfg,
    platform_names, install_targets, glblcfg, expect, caplog
):
    def flatten_install_targets_map(itm):
        result = {}
        for target, platforms in itm.items():
            result[target] = sorted([p['name'] for p in platforms])
        return result

    mock_glbl_cfg('cylc.flow.platforms.glbl_cfg', glblcfg)

    install_targets_map = TaskRemoteMgr._get_remote_tidy_targets(
        set(platform_names), set(install_targets))

    with suppress(KeyError):
        install_targets_map.pop('localhost')

    assert (
        expect['targets'] == flatten_install_targets_map(install_targets_map))

    if expect['unreachable']:
        for unreachable in expect["unreachable"]:
            assert (
                unreachable in caplog.records[0].msg)
    else:
        assert not caplog.records


shared_eval_params = [
    pytest.param(
        'localhost', {}, 'localhost', id="localhost"
    ),
    pytest.param(
        '$(some-cmd)', {}, None, id="subshell_1st_eval"
    ),
    pytest.param(
        '$(some-cmd)', {'some-cmd': None}, None,
        id="subshell_awaiting_eval"
    ),
    pytest.param(
        '$(some-cmd)', {'some-cmd': 'isaac clarke'}, 'isaac clarke',
        id="subshell_finished_eval"
    ),
    pytest.param(
        '$SOME_ENV', {}, 'nolan stross', id="env_var"
    ),
    pytest.param(
        '$(env-cmd)', {'env-cmd': '$SOME_ENV'}, 'nolan stross',
        id="subshell_env_var"
    ),
    pytest.param(
        'titan_station', {}, 'titan_station', id="verbatim_name"
    ),
    pytest.param(
        '', {}, 'localhost', id="empty"
    ),
]


@pytest.fixture
def task_remote_mgr_eval(monkeypatch: pytest.MonkeyPatch):
    """Fixture providing a task remote manager for eval_platform() &
    eval_host() tests."""
    def _task_remote_mgr_eval(remote_cmd_map: dict) -> TaskRemoteMgr:
        monkeypatch.setenv('SOME_ENV', 'nolan stross')
        task_remote_mgr = TaskRemoteMgr(
            workflow='usg_ishimura',
            proc_pool=Mock(),
            bad_hosts=[],
            db_mgr=None,
            server=None
        )
        task_remote_mgr.remote_command_map = remote_cmd_map
        return task_remote_mgr

    return _task_remote_mgr_eval


@pytest.mark.parametrize(
    'eval_str, remote_cmd_map, expected',
    [
        *shared_eval_params,
        pytest.param(
            'localhost_tau_volantis', {}, 'localhost_tau_volantis',
            id="name_begin_w_localhost"
        )
    ]
)
def test_eval_platform(
    eval_str: str, remote_cmd_map: dict, expected: Optional[str],
    task_remote_mgr_eval,
):
    task_remote_mgr: TaskRemoteMgr = task_remote_mgr_eval(remote_cmd_map)
    assert task_remote_mgr.eval_platform(eval_str) == expected


def test_eval_platform_bad(task_remote_mgr_eval):
    exc_msg = "foreign contaminant detected"
    task_remote_mgr: TaskRemoteMgr = task_remote_mgr_eval(
        {'cmd': PlatformError(exc_msg, 'aegis_vii')}
    )
    with pytest.raises(PlatformError, match=exc_msg):
        task_remote_mgr.eval_platform('$(cmd)')


@pytest.mark.parametrize(
    'eval_str, remote_cmd_map, expected',
    [
        *shared_eval_params,
        pytest.param(
            'localhost4.localdomain4', {}, 'localhost', id="localhost_variant"
        ),
        pytest.param(
            '`other cmd`', {'other cmd': 'nicole brennan'}, 'nicole brennan',
            id="backticks"
        ),
    ]
)
def test_eval_host(
    eval_str: str, remote_cmd_map: dict, expected: Optional[str],
    task_remote_mgr_eval,
):
    task_remote_mgr: TaskRemoteMgr = task_remote_mgr_eval(remote_cmd_map)
    assert task_remote_mgr.eval_host(eval_str) == expected
