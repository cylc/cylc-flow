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

from typing import Callable
from unittest.mock import Mock


from cylc.flow.xtriggers.workflow_state import workflow_state
from ..conftest import MonkeyMock


def test_inferred_run(tmp_run_dir: Callable, monkeymock: MonkeyMock):
    """Test that the workflow_state xtrigger infers the run number"""
    reg = 'isildur'
    expected_workflow_id = f'{reg}/run1'
    cylc_run_dir = str(tmp_run_dir())
    tmp_run_dir(expected_workflow_id, installed=True, named=True)
    mock_db_checker = monkeymock(
        'cylc.flow.xtriggers.workflow_state.CylcWorkflowDBChecker',
        return_value=Mock(
            get_remote_point_format=lambda: 'CCYY',
        )
    )

    _, results = workflow_state(reg, task='precious', point='3000')
    mock_db_checker.assert_called_once_with(cylc_run_dir, expected_workflow_id)
    assert results['workflow'] == expected_workflow_id
