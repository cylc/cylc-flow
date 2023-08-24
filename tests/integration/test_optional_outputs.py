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

"""Test optional output functionality.

See the proposals:
* https://cylc.github.io/cylc-admin/proposal-new-output-syntax.html
* https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html
"""

from unittest.mock import Mock

import pytest

from cylc.flow.exceptions import (
    GraphParseError,
    WorkflowConfigError,
)
from cylc.flow.task_outputs import (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
    get_completion_expression,
)
from cylc.flow.task_state import TASK_STATUS_EXPIRED


async def test_workflow_stalls_if_no_opt_output_generated_1(
    flow,
    scheduler,
    start,
    log_filter,
):
    """It should stall if zero optional outputs are generated.

    Example 1: succeeded and (x or y)

    Tests proposal point (2)
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    a:x? => x
                    a:y? => y
                '''
            }
        },
        'runtime': {
            'a': {
                'outputs': {
                    'x': 'x',
                    'y': 'y',
                }
            },
            'x, y': {},
        }
    })
    schd = scheduler(id_)
    async with start(schd) as log:
        # set 1/a to succeeded without generating x or y
        task_a = schd.pool.get_task('1', 'a')
        task_a.state_reset(TASK_OUTPUT_SUCCEEDED)

        # the workflow should be stalled
        assert schd.pool.is_stalled()

        # this can get logged by two different interfaces
        assert log_filter(
            # automatically - when the task finishes
            log,
            contains="1/a did not complete required outputs: ['x', 'y']",
        )
        log.clear()
        schd.pool.log_incomplete_tasks()
        assert log_filter(
            # via log_incomplete_tasks - called on shutdown
            log,
            contains="1/a did not complete required outputs: ['x', 'y']",
        )

        # set output x
        schd.pool.spawn_on_output(task_a, 'x')

        # the workflow should be unstalled
        schd.is_stalled = None  # reset stall status
        assert not schd.pool.is_stalled()


async def test_workflow_stalls_if_no_opt_output_generated_2(
    flow,
    scheduler,
    start,
):
    """It should stall if zero optional outputs are generated.

    Example 2: succeeded  # but we actually want "succeeded or failed"

    Because there is no failure pathway defined in this example, Cylc will
    stall as it cannot determine the user's intention. To avoid this a failure
    pathway must be provided in the graph, if there is no failure pathway
    (i.e. `a:fail => null`) a completion expression can be written to tolerate
    task failure.

    Tests proposal point (2)
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md
    """
    raw = {
        'scheduling': {
            'graph': {
                'R1': '''
                    a? => x
                '''
            },
        },
        'runtime': {'a': {}, 'x': {}}
    }

    id_ = flow(raw)
    schd = scheduler(id_)
    async with start(schd):
        # one or more optional outputs must be completed so, in the absense of
        # an alternative pathway "succeeded" is required
        task_a = schd.pool.get_task('1', 'a')
        assert task_a.state.outputs._completion_expression == 'succeeded'

        # if 1/a fails, the workflow should stall
        task_a.state_reset(TASK_OUTPUT_FAILED)
        assert schd.pool.is_stalled()

    # to avoid stall in the event of failure the user must configure a failure
    # pathway, either by `a:fail? => something` or by using a completion
    # expression
    raw['runtime']['a']['completion'] = 'succeeded or failed'

    # the workflow should *not* stall if 1/a fails
    id_ = flow(raw)
    schd = scheduler(id_)
    async with start(schd):
        # Cylc now knows that failure is expected and ok
        task_a = schd.pool.get_task('1', 'a')
        assert task_a.state.outputs._completion_expression == (
            'succeeded or failed'
        )

        # so the workflow should not stall if 1/a fails
        task_a.state_reset(TASK_OUTPUT_FAILED)
        assert not schd.pool.is_stalled()


async def test_completion_expression(
    flow,
    scheduler,
    start,
    monkeypatch,
):
    """The task completion condition should be customisable.

    Tests proposal point (3)
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md
    """
    mock_remove = Mock()
    monkeypatch.setattr(
        'cylc.flow.task_pool.TaskPool.remove',
        mock_remove,
    )

    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a?',
            },
        },
        'runtime': {
            'a': {
                'completion': '(succeeded and x) or (failed and y)',
                'outputs': {'x': 'x', 'y': 'y'},
            },
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        # complete the "succeeded" output
        itask = schd.pool.get_task('1', 'a')
        itask.state.outputs.set_completion(TASK_OUTPUT_SUCCEEDED, True)

        # the task should *not* be removed from the pool as complete
        schd.pool.remove_if_complete(itask)
        assert mock_remove.call_count == 0

        # complete the "x" output
        itask.state.outputs.set_completion('x', True)

        # the task *should* be removed from the pool as complete
        schd.pool.remove_if_complete(itask)
        assert mock_remove.call_count == 1


def test_validate_completion_expression(
    flow,
    validate,
    monkeypatch,
):
    """It should validate the completion expression itself.

    Tests the validation side of proposal point (3)
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md
    """
    config = {
        'scheduling': {
            'graph': {
                'R1': 'a?',
            },
        },
        'runtime': {
            'a': {
                'completion': 'succeeded or failed'
            }
        }
    }
    id_ = flow(config)

    # it should fail validation in back-compat mode
    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', True)
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert 'compatibility mode' in str(exc_ctx.value)

    # but validate fine otherwise
    monkeypatch.setattr('cylc.flow.flags.cylc7_back_compat', False)
    validate(id_)

    # it should fail if we reference outputs which haven't been registered
    config['runtime']['a']['completion'] = 'succeeded or (failed and x)'
    id_ = flow(config)
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert '[runtime][a]completion' in str(exc_ctx.value)
    assert "Input 'x' is not defined" in str(exc_ctx.value)

    # it should be happy once we're registered those outputs
    config['runtime']['a']['outputs'] = {'x': 'x'}
    id_ = flow(config)
    validate(id_)

    # it should error on invalid syntax
    config['runtime']['a']['completion'] = '!succeeded'
    id_ = flow(config)
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert '[runtime][a]completion' in str(exc_ctx.value)
    assert "invalid syntax" in str(exc_ctx.value)
    assert "!succeeded" in str(exc_ctx.value)

    # it should error on restricted syntax
    config['runtime']['a']['completion'] = '__import__("os")'
    id_ = flow(config)
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert '[runtime][a]completion' in str(exc_ctx.value)
    assert '__import__("os")' in str(exc_ctx.value)
    assert '"Call" not permitted' in str(exc_ctx.value)

    # it should give a helpful error message when submit-failed is used
    config['runtime']['a']['completion'] = 'submit-failed'
    id_ = flow(config)
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert '[runtime][a]completion' in str(exc_ctx.value)
    assert (
        'Use "submit_failed" rather than "submit-failed"'
    ) in str(exc_ctx.value)

    # it should accept "submit_failed"
    config['runtime']['a']['completion'] = 'submit_failed'
    id_ = flow(config)
    validate(id_)

    # it should give a generic warning when hypens are used
    config['runtime']['a']['completion'] = 'a-b - c'
    id_ = flow(config)
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert '[runtime][a]completion' in str(exc_ctx.value)
    assert 'Replace hyphens with underscores' in str(exc_ctx.value)


def test_clock_expire_implies_optional_expiry(
    flow,
    validate,
):
    """Expiry must be an optional output when clock-expiry is configured.

    Tests proposal point (5)
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md
    """
    config = {
        'scheduling': {
            'initial cycle point': '2000',
            'special tasks': {
                'clock-expire': 'a',
            },
            'graph': {
                # * a:expired? is not referenced in the graph
                #   but is still optional because it's clock-expired
                # * a:succeeded cannot be required if a:expired is optional
                'P1D': 'a'
            },
        },
        'runtime': {
            'a': {},
        }
    }

    # it should fail validation because "a:succeeded" must be optional
    id_ = flow(config)
    with pytest.raises(GraphParseError) as exc_ctx:
        validate(id_)
    assert (
        'Opposite outputs a:succeeded and a:expired must both be optional'
    ) in str(exc_ctx.value)

    # when we correct this is should pass vallidation
    config['scheduling']['graph']['P1D'] = 'a?'
    id_ = flow(config)
    cfg = validate(id_)
    taskdef = cfg.taskdefs['a']

    # expired and succeeded should both be optional outputs
    assert taskdef.outputs[TASK_OUTPUT_EXPIRED][1] is False
    assert taskdef.outputs[TASK_OUTPUT_SUCCEEDED][1] is False
    assert get_completion_expression(taskdef) == (
        'expired or succeeded'
    )


async def test_expiry_is_considered_for_tasks_with_partially_sat_prereqs(
    flow,
    scheduler,
    start,
    monkeypatch,
):
    """We should capture expiry events as soon as a task is spawned.

    To allow expiry events to be captured early (as opposed to at the time of
    submission) e.g. for catchup logic, we need to consider tasks for expiry
    as soon as any of their prereqs are satisfied (subject to runahead
    constraints).

    Tests proposal point (6):
    https://github.com/cylc/cylc-admin/blob/master/docs/proposal-optional-output-extension.md
    """
    # prevent expired tasks being removed from the pool for ease of testing
    monkeypatch.setattr(
        'cylc.flow.task_pool.TaskPool.remove',
        Mock(),
    )

    start_year = 2000
    runahead_limit = 3
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
            'cycle point format': 'CCYY',
        },
        'scheduling': {
            'initial cycle point': str(start_year),
            'runahead limit': f'P{runahead_limit}',
            'special tasks': {
                'clock-expire': 'a',
            },
            'graph': {
                'P1Y': '''
                    # this parentless task ensures "a" gets spawned when it is
                    # within the runahead window
                    head_of_cycle
                    a[-P1Y]? & head_of_cycle => a?
                    a:expire? => catchup
                    a? => continue
                '''
            },
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # all cycle points *within* the runahead limit
        runahead_window = [
            str(year)
            for year in range(start_year, start_year + runahead_limit)
        ]

        # mark the "head_of_cycle" task as succeeded for each cycle within the
        # runahead window
        for cycle in runahead_window:
            itask = schd.pool.get_task(cycle, 'head_of_cycle')
            schd.pool.spawn_on_output(itask, TASK_OUTPUT_SUCCEEDED)

        # run the expiry logic
        assert schd.pool.set_expired_tasks()

        # check which tasks were expired
        assert {
            # tasks marked as expired in the pool
            itask.tokens.relative_id
            for itask in schd.pool.get_all_tasks()
            if itask.state(TASK_STATUS_EXPIRED)
        } == {
            # tasks we would expect to have been expired
            schd.tokens.duplicate(cycle=cycle, task='a').relative_id
            for cycle in runahead_window
        }


def test_validate_optional_outputs_graph_and_completion(
    flow,
    validate,
):
    """It should error if optional outputs are required elsewhere.

    Ensure the use of optional outputs is consistent between the graph and
    completion expression if defined.
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': '''
                    a:succeeded? => s
                    a:expired? => e
                '''
            }
        },
        'runtime': {
            'a': {
                'completion': 'expired',
            }
        }
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert str(exc_ctx.value) == (
        'a:expired is optional in the graph (? symbol),'
        ' but required in the completion expression.'
    )

    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'graph': {
                'R1': '''
                    a:succeeded => s
                '''
            }
        },
        'runtime': {
            'a': {
                'completion': 'succeeded or expired',
            }
        }
    })
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert str(exc_ctx.value) == (
        'a:succeeded is optional in the completion expression,'
        ' but required in the graph (? symbol).'
    )
