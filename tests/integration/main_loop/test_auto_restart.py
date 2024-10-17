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

import asyncio
from unittest.mock import Mock

import pytest

from cylc.flow.main_loop import MainLoopPluginException
from cylc.flow.scheduler import Scheduler
from cylc.flow.workflow_status import AutoRestartMode


async def test_no_detach(
    one_conf, flow, scheduler, run, mock_glbl_cfg, log_filter,
    monkeypatch: pytest.MonkeyPatch
):
    """Test that the Scheduler aborts when auto restart tries to happen
    while in no-detach mode."""
    mock_glbl_cfg(
        'cylc.flow.scheduler.glbl_cfg', '''
        [scheduler]
            [[main loop]]
                plugins = auto restart
                [[[auto restart]]]
                    interval = PT1S
    ''')
    monkeypatch.setattr(
        'cylc.flow.main_loop.auto_restart._should_auto_restart',
        Mock(return_value=AutoRestartMode.RESTART_NORMAL)
    )
    id_: str = flow(one_conf)
    schd: Scheduler = scheduler(id_, paused_start=True, no_detach=True)
    with pytest.raises(MainLoopPluginException) as exc:
        async with run(schd):
            await asyncio.sleep(2)
    assert log_filter(contains=f"Workflow shutting down - {exc.value}")
