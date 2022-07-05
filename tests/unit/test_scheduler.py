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

import pytest
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import Mock

from cylc.flow.exceptions import InputError
from cylc.flow.scheduler import Scheduler
from cylc.flow.scheduler_cli import RunOptions

Fixture = Any


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
