#!/usr/bin/env python3

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

from cylc.flow.exceptions import (
    GraphParseError,
    WorkflowConfigError,
    WorkflowFilesError,
)
from cylc.flow.scripts.validate import (
    ValidateOptions,
    run as validate,
)
from cylc.flow.workflow_files import WorkflowFiles


async def test_suite_rc(tmp_path):
    """It should reject workflows with suite.rc files."""
    # suite.rc present
    (tmp_path / WorkflowFiles.SUITE_RC).touch()
    with pytest.raises(WorkflowFilesError, match=f'No flow.cylc.*{tmp_path}'):
        await validate(ValidateOptions(), str(tmp_path))

    # suite.rc and flow.cylc present
    (tmp_path / WorkflowFiles.FLOW_FILE).touch()
    with pytest.raises(
        WorkflowFilesError, match=f'Both flow.cylc and suite.rc.*{tmp_path}'
    ):
        await validate(ValidateOptions(), str(tmp_path))

    # flow.cylc present
    (tmp_path / WorkflowFiles.SUITE_RC).unlink()
    with pytest.raises(WorkflowConfigError):
        await validate(ValidateOptions(), str(tmp_path))


async def test_opposite_outputs(flow, validate):
    """Test logically opposite outputs are reported if misused."""
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    foo => bar
                    foo:fail => baz
                    foo => !baz
                '''
            },
        },
    })
    with pytest.raises(
        GraphParseError,
        match=(
            'Opposite outputs foo:failed and foo:succeeded must both be'
            ' optional if both are used'
        ),
    ):
        validate(id_)
