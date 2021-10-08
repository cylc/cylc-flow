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
        ('_cylc', False),
        ('_cylcy', False),
    ]
)
def test_validate_task_name(
    flow,
    one_conf,
    validate,
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

    if valid:
        validate(reg)
    else:
        with pytest.raises(WorkflowConfigError) as exc_ctx:
            validate(reg)
        assert task_name in str(exc_ctx.value)


@pytest.mark.parametrize(
    'task_name',
    [
        'root',
        '_cylc',
        '_cylcy',
    ]
)
def test_validate_implicit_task_name(
    flow,
    validate,
    task_name: str,
):
    """It should validate implicit task names in the graph.

    Note that most invalid task names get caught during graph parsing.
    Here we ensure that names which look like valid graph node names but which
    are blacklisted get caught and raise errors.
    """
    reg = flow({
        'scheduler': {
            'allow implicit tasks': 'True'
        },
        'scheduling': {
            'graph': {
                'R1': task_name
            }
        },
        'runtime': {
            # having one item in the runtime allows "root" to be expanded
            # which makes this test more thorough
            'whatever': {}
        }
    })

    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(reg)
    assert str(exc_ctx.value).splitlines()[0] == (
        f'invalid task name "{task_name}"'
    )
