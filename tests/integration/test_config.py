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
from functools import partial
from pathlib import Path

import pytest

from cylc.flow.config import WorkflowConfig
from cylc.flow.scripts.validate import ValidateOptions
from cylc.flow.exceptions import WorkflowConfigError


@pytest.mark.parametrize(
    'task_name,valid', [
        # valid task names
        ('a', True),
        ('a-b', True),
        ('a_b', True),
        ('foo', True),
        ('0aA-+%', True),
        # invalid task names
        ('a b', False),
        ('a£b', False),
        ('+ab', False),
        ('@ab', False),  # not valid in [runtime]
    ]
)
def test_validate_task_name(
    flow,
    one_conf,
    run_dir,
    task_name: str,
    valid: bool
):
    """It should raise errors for invalid task names in the runtime section."""
    reg = flow({
        **one_conf,
        'runtime': {
            task_name: {}
        }
    })

    validate = partial(
        WorkflowConfig,
        reg,
        str(Path(run_dir, reg, 'flow.cylc')),
        ValidateOptions()
    )

    if valid:
        validate()
    else:
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            validate()
        assert task_name in str(exc_ctx.value)
