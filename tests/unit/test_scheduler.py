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
"""Tests for Cylc scheduler server."""

import logging
import socket
from time import time
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock, Mock

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import InputError
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import RunOptions
from cylc.flow.task_pool import TaskPool
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.workflow_status import AutoRestartMode


@pytest.mark.parametrize(
    'opts_to_test, is_restart, err_msg',
    [
        pytest.param(
            ['icp', 'startcp', 'starttask'],
            True,
            "option --{} is not valid for restart",
            id="start opts on restart"
        ),
        pytest.param(
            ['icp', 'startcp', 'starttask'],
            False,
            "option --{}=reload is not valid",
            id="start opts =reload"
        ),
        pytest.param(
            ['fcp', 'stopcp'],
            False,
            "option --{}=reload is only valid for restart",
            id="end opts =reload when not restart"
        ),
    ]
)
def test_check_startup_opts(
    opts_to_test: List[str],
    is_restart: bool,
    err_msg: str
) -> None:
    """Test Scheduler._check_startup_opts()"""
    for opt in opts_to_test:
        mocked_scheduler = Mock(is_restart=is_restart)
        mocked_scheduler.options = SimpleNamespace(**{opt: 'reload'})
        with pytest.raises(InputError) as excinfo:
            Scheduler._check_startup_opts(mocked_scheduler)
        assert(err_msg.format(opt) in str(excinfo))


@pytest.mark.parametrize(
    'auto_restart_time, expected',
    [
        (-1, True),
        (0, True),
        (1, False),
        (None, False),
    ]
)
def test_should_auto_restart_now(
    auto_restart_time, expected, monkeypatch: pytest.MonkeyPatch
):
    """Test Scheduler.should_auto_restart_now()."""
    time_now = time()
    monkeypatch.setattr('cylc.flow.scheduler.time', lambda: time_now)
    if auto_restart_time is not None:
        auto_restart_time += time_now
    mock_schd = Mock(spec=Scheduler, auto_restart_time=auto_restart_time)
    assert Scheduler.should_auto_restart_now(mock_schd) == expected


def test_release_tasks_to_run__auto_restart():
    """Test that Scheduler.release_tasks_to_run() works as expected
    during auto restart."""
    mock_schd = Mock(
        auto_restart_time=(time() - 100),
        auto_restart_mode=AutoRestartMode.RESTART_NORMAL,
        is_paused=False,
        stop_mode=None,
        pool=Mock(
            spec=TaskPool,
            get_tasks=lambda: [Mock(spec=TaskProxy)]
        ),
        workflow='parachutes',
        options=RunOptions(),
        task_job_mgr=MagicMock()
    )
    Scheduler.release_tasks_to_run(mock_schd)
    # Should not actually release any more tasks, just submit the
    # preparing ones
    mock_schd.pool.release_queued_tasks.assert_not_called()

    Scheduler.start_job_submission(mock_schd, mock_schd.pool.get_tasks())
    mock_schd.task_job_mgr.submit_task_jobs.assert_called()


def test_auto_restart_DNS_error(monkeypatch, caplog, log_filter):
    """Ensure that DNS errors in host selection are caught."""
    def _select_workflow_host(cached=False):
        # fake a "get address info" error
        # this error can occur due to an unknown host resulting from broken
        # DNS or an invalid host name in the global config
        raise socket.gaierror('elephant')

    monkeypatch.setattr(
        'cylc.flow.scheduler.select_workflow_host',
        _select_workflow_host,
    )
    schd = Mock(
        workflow='myworkflow',
        options=RunOptions(abort_if_any_task_fails=False),
        INTERVAL_AUTO_RESTART_ERROR=0,
    )
    caplog.set_level(logging.ERROR, CYLC_LOG)
    assert not Scheduler.workflow_auto_restart(schd, max_retries=2)
    assert log_filter(contains='elephant')


def test_auto_restart_popen_error(monkeypatch, caplog, log_filter):
    """Ensure that subprocess errors are handled."""
    def _select_workflow_host(cached=False):
        # mock a host-select return value
        return ('foo', 'foo')

    monkeypatch.setattr(
        'cylc.flow.scheduler.select_workflow_host',
        _select_workflow_host,
    )

    def _popen(*args, **kwargs):
        # mock an auto-restart command failure
        return Mock(
            wait=lambda: 1,
            communicate=lambda: ('mystdout', 'mystderr'),
        )

    monkeypatch.setattr(
        'cylc.flow.scheduler.Popen',
        _popen,
    )

    schd = Mock(
        workflow='myworkflow',
        options=RunOptions(abort_if_any_task_fails=False),
        INTERVAL_AUTO_RESTART_ERROR=0,
    )
    caplog.set_level(logging.ERROR, CYLC_LOG)
    assert not Scheduler.workflow_auto_restart(schd, max_retries=2)
    assert log_filter(contains='mystderr')
