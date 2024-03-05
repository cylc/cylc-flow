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

from typing import Optional
from unittest.mock import Mock, patch

import pytest

from cylc.flow.broadcast_mgr import BroadcastMgr
from cylc.flow.subprocctx import SubProcContext
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.taskdef import TaskDef


@patch("cylc.flow.task_events_mgr.LOG")
def test_log_error_on_error_exit_code(cylc_log):
    """Test that an error log is emitted when the log retrieval command
    exited with a code different than zero.

    :param cylc_log: mocked cylc logger
    :type cylc_log: mock.MagicMock
    """
    task_events_manager = TaskEventsManager(
        None, None, None, None, None, None, None, None, None)
    proc_ctx = SubProcContext(
        cmd_key=None, cmd="error", ret_code=1, err="Error!", id_keys=[])
    task_events_manager._job_logs_retrieval_callback(proc_ctx, None)
    assert cylc_log.error.call_count == 1
    assert cylc_log.error.call_args.contains("Error!")


@patch("cylc.flow.task_events_mgr.LOG")
def test_log_debug_on_noerror_exit_code(cylc_log):
    """Test that a debug log is emitted when the log retrieval command
    exited with an non-error code (i.e. 0).

    :param cylc_log: mocked cylc logger
    :type cylc_log: mock.MagicMock
    """
    task_events_manager = TaskEventsManager(
        None, None, None, None, None, None, None, None, None)
    proc_ctx = SubProcContext(
        cmd_key=None, cmd="ls /tmp/123", ret_code=0, err="", id_keys=[])
    task_events_manager._job_logs_retrieval_callback(proc_ctx, None)
    assert cylc_log.debug.call_count == 1
    assert cylc_log.debug.call_args.contains("ls /tmp/123")


@pytest.mark.parametrize(
    "broadcast, remote, platforms, expected",
    [
        ("hpc1", "a", "b", "hpc1"),
        (None, "hpc1", "b", "hpc1"),
        (None, None, "hpc1", "hpc1"),
        (None, None, None, None),
    ]
)
def test_get_remote_conf(broadcast, remote, platforms, expected):
    """Test TaskEventsManager._get_remote_conf()."""

    task_events_mgr = TaskEventsManager(
        None, None, None, None, None, None, None, None, None)

    task_events_mgr.broadcast_mgr = Mock(
        get_broadcast=lambda x: {
            "remote": {
                "host": broadcast
            }
        }
    )

    itask = Mock(
        identity='foo.1',
        tdef=Mock(
            rtconfig={
                'remote': {
                    'host': remote
                }
            }
        ),
        platform={
            'host': platforms
        }
    )

    assert task_events_mgr._get_remote_conf(itask, 'host') == expected


@pytest.mark.parametrize(
    "broadcast, workflow, platforms, expected",
    [
        ([800], [700], [600], [800]),
        (None, [700], [600], [700]),
        (None, None, [600], [600]),
    ]
)
def test_get_workflow_platforms_conf(broadcast, workflow, platforms, expected):
    """Test TaskEventsManager._get_polling_interval_conf()."""

    task_events_mgr = TaskEventsManager(
        None, None, None, None, None, None, None, None, None)

    KEY = "execution polling intervals"

    task_events_mgr.broadcast_mgr = Mock(
        get_broadcast=lambda x: {
            KEY: broadcast
        }
    )

    itask = Mock(
        identity='foo.1',
        tdef=Mock(
            rtconfig={
                KEY: workflow
            }
        ),
        platform={
            KEY: platforms
        }
    )

    assert (
        task_events_mgr._get_workflow_platforms_conf(itask, KEY) ==
        expected
    )


@pytest.mark.parametrize(
    'rt_val, schd_val, glbl_val, expected',
    [
        ('rt', 'schd', 'glbl', 'rt'),
        (None, 'schd', 'glbl', 'schd'),
        (None, None, 'glbl', 'glbl'),
        (None, None, None, 'default'),
    ]
)
def test_get_events_conf__mail_to_from(
    mock_glbl_cfg,
    rt_val: Optional[str],
    schd_val: Optional[str],
    glbl_val: Optional[str],
    expected: str
):
    """Test order of precedence for [mail]to/from."""
    if glbl_val:
        mock_glbl_cfg(
            'cylc.flow.task_events_mgr.glbl_cfg',
            f'''
            [scheduler]
                [[mail]]
                    from = {glbl_val}
                    to = {glbl_val}
            '''
        )

    mock_task = Mock(
        spec=TaskProxy,
        tdef=Mock(
            spec=TaskDef,
            rtconfig={
                'events': {},
                'mail': {'to': rt_val, 'from': rt_val} if rt_val else {},
            },
        ),
    )
    mock_task_events_mgr = Mock(
        spec=TaskEventsManager,
        workflow_cfg={
            'scheduler': {
                'mail': {'to': schd_val, 'from': schd_val},
            },
        } if schd_val else {},
        broadcast_mgr=Mock(
            spec_set=BroadcastMgr,
            get_broadcast=lambda *a, **k: {},
        ),
    )

    for key in ('to', 'from'):
        assert TaskEventsManager._get_events_conf(
            mock_task_events_mgr, itask=mock_task, key=key, default='default'
        ) == expected
