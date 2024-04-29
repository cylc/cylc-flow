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

import pytest

from cylc.flow.task_state import (
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_FAILED
)
from cylc.flow.task_state_prop import extract_group_state


def test_extract_group_state_childless():
    assert extract_group_state(child_states=[]) is None


@pytest.mark.parametrize("child_states, is_stopped, expected", [
    (
        [TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED],
        False,
        TASK_STATUS_SUBMIT_FAILED
    ),
    (
        ["Who?", TASK_STATUS_FAILED],
        False,
        TASK_STATUS_FAILED
    )
])
def test_extract_group_state_order(child_states, is_stopped, expected):
    assert extract_group_state(
        child_states=child_states, is_stopped=is_stopped
    ) == expected
