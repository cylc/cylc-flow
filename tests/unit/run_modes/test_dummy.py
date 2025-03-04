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
"""Tests for utilities supporting dummy mode.
"""
import pytest
from cylc.flow.run_modes.dummy import build_dummy_script


@pytest.mark.parametrize(
    'fail_one_time_only', (True, False)
)
def test_build_dummy_script(fail_one_time_only):
    rtc = {
        'outputs': {'foo': '1', 'bar': '2'},
        'simulation': {
            'fail try 1 only': fail_one_time_only,
            'fail cycle points': '1',
        }
    }
    result = build_dummy_script(rtc, 60)
    assert result.split('\n') == [
        'sleep 60',
        "cylc message '1'",
        "cylc message '2'",
        f"cylc__job__dummy_result {str(fail_one_time_only).lower()}"
        " 1 || exit 1"
    ]
