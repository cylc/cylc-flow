# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
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

from cylc.flow.exceptions import WorkflowFilesError

import pytest

from cylc.flow.workflow_files import WorkflowFiles


async def test_suite_rc(tmp_path, install):
    """It should reject workflows with suite.rc files."""
    # suite.rc present
    (tmp_path / WorkflowFiles.SUITE_RC).touch()
    with pytest.raises(WorkflowFilesError, match=f'No flow.cylc.*{tmp_path}'):
        await install(tmp_path, run_name='1')

    # suite.rc and flow.cylc present
    (tmp_path / WorkflowFiles.FLOW_FILE).touch()
    with pytest.raises(
        WorkflowFilesError, match=f'Both flow.cylc and suite.rc.*{tmp_path}'
    ):
        await install(tmp_path, run_name='2')

    # flow.cylc present
    (tmp_path / WorkflowFiles.SUITE_RC).unlink()
    await install(tmp_path, run_name='3')
