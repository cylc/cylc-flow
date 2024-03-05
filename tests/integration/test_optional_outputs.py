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

"""Tests optional output and task completion logic.

This functionality is defined by the "optional-output-extension" proposal:

https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
"""

from itertools import combinations
from typing import TYPE_CHECKING

import pytest

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.network.resolvers import TaskMsg
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_events_mgr import (
    TaskEventsManager,
)
from cylc.flow.task_outputs import (
    TASK_OUTPUTS,
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FINISHED,
    TASK_OUTPUT_SUCCEEDED,
    get_completion_expression,
)
from cylc.flow.task_state import (
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_WAITING,
)

if TYPE_CHECKING:
    from cylc.flow.task_proxy import TaskProxy


def reset_outputs(itask: 'TaskProxy'):
    """Undo the consequences of setting task outputs.

    This assumes you haven't completed the task.
    """
    itask.state.outputs._completed = {
        message: False
        for message in itask.state.outputs._completed
    }
    itask.state_reset(
        TASK_STATUS_WAITING,
        is_queued=False,
        is_held=False,
        is_runahead=False,
    )


@pytest.mark.parametrize(
    'graph, completion_outputs',
    [
        pytest.param(
            'a:x',
            [{TASK_OUTPUT_SUCCEEDED, 'x'}],
            id='1',
        ),
        pytest.param(
            'a\na:x\na:expired?',
            [{TASK_OUTPUT_SUCCEEDED, 'x'}, {TASK_OUTPUT_EXPIRED}],
            id='2',
        ),
    ],
)
async def test_task_completion(
    flow,
    scheduler,
    start,
    graph,
    completion_outputs,
    capcall,
):
    """Ensure that task completion is watertight.

    Run through every possible permutation of outputs MINUS the ones that would
    actually complete a task to ensure that task completion is correctly
    handled.

    Note, the building and evaluation of completion expressions is also tested,
    this is more of an end-to-end test to ensure everything is connected
    properly.
    """
    # prevent tasks from being removed from the pool when complete
    capcall(
        'cylc.flow.task_pool.TaskPool.remove_if_complete'
    )
    id_ = flow({
        'scheduling': {
            'graph': {'R1': graph},
        },
        'runtime': {
            'a': {
                'outputs': {
                    'x': 'xxx',
                },
            },
        },
    })
    schd = scheduler(id_)
    all_outputs = {
        # all built-in outputs
        *TASK_OUTPUTS,
        # all registered custom outputs
        'x'
        # but not the finished psudo output
    } - {TASK_OUTPUT_FINISHED}

    async with start(schd):
        a1 = schd.pool.get_task(IntegerPoint('1'), 'a')

        # try every set of outputs that *shouldn't* complete the task
        for combination in {
            comb
            # every possible combination of outputs
            for _length in range(1, len(all_outputs))
            for comb in combinations(all_outputs, _length)
            # that doesn't contain the outputs that would satisfy the task
            if not any(
                set(comb) & output_set == output_set
                for output_set in completion_outputs
            )
        }:
            # set the combination of outputs
            schd.pool.set_prereqs_and_outputs(
                ['1/a'],
                combination,
                [],
                ['1'],
            )

            # ensure these outputs do *not* complete the task
            assert not a1.state.outputs.is_complete()

            # reset any changes
            reset_outputs(a1)

        # now try the outputs that *should* satisfy the task
        for combination in completion_outputs:
            # set the combination of outputs
            schd.pool.set_prereqs_and_outputs(
                ['1/a'],
                combination,
                [],
                ['1'],
            )

            # ensure the task *is* completed
            assert a1.state.outputs.is_complete()

            # reset any changes
            reset_outputs(a1)


async def test_expire_orthogonality(flow, scheduler, start):
    """Ensure "expired?" does not infer "succeeded?".

    Asserts proposal point 2:
    https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a:expire? => e'
            },
        },
    })
    schd: 'Scheduler' = scheduler(id_, paused_start=False)
    async with start(schd):
        a_1 = schd.pool.get_task(IntegerPoint('1'), 'a')

        # wait for the task to submit
        while not a_1.state(TASK_STATUS_WAITING, TASK_STATUS_PREPARING):
            schd.release_queued_tasks()

        # NOTE: The submit number isn't presently incremented via this code
        # pathway so we have to hack it here. If the task messages in this test
        # get ignored because of some future change, then you can safely remove
        # this line (it's not what this test is testing).
        a_1.submit_num += 1

        # tell the scheduler that the task *submit-failed*
        schd.message_queue.put(
            TaskMsg(
                '1/a/01',
                '2000-01-01T00:00:00+00',
                'INFO',
                TaskEventsManager.EVENT_SUBMIT_FAILED
            ),
        )
        schd.process_queued_task_messages()
        # ensure that the scheduler is stalled
        assert not a_1.state.outputs.is_complete()
        assert schd.pool.is_stalled()

        # tell the scheduler that the task *failed*
        schd.message_queue.put(
            TaskMsg(
                '1/a/01',
                '2000-01-01T00:00:00+00',
                'INFO',
                TaskEventsManager.EVENT_FAILED,
            ),
        )
        schd.process_queued_task_messages()
        # ensure that the scheduler is stalled
        assert not a_1.state.outputs.is_complete()
        assert schd.pool.is_stalled()

        # tell the scheduler that the task *expired*
        schd.message_queue.put(
            TaskMsg(
                '1/a/01',
                '2000-01-01T00:00:00+00',
                'INFO',
                TaskEventsManager.EVENT_EXPIRED,
            ),
        )
        schd.process_queued_task_messages()
        # ensure that the scheduler is *not* stalled
        assert a_1.state.outputs.is_complete()
        assert not schd.pool.is_stalled()


@pytest.fixture(scope='module')
def implicit_completion_config(mod_flow, mod_validate):
    id_ = mod_flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    a

                    b?

                    c:x

                    d:x?
                    d:y?
                    d:z?

                    e:x
                    e:y
                    e:z

                    f?
                    f:x

                    g:expired?

                    h:succeeded?
                    h:expired?

                    i:expired?
                    i:submitted

                    j:expired?
                    j:submitted?

                    k:submit-failed?
                    k:succeeded?

                    l:expired?
                    l:submit-failed?
                    l:succeeded?
                '''
            }
        },
        'runtime': {
            'root': {
                'outputs': {
                    'x': 'xxx',
                    'y': 'yyy',
                    'z': 'zzz',
                }
            }
        }
    })
    return mod_validate(id_)


@pytest.mark.parametrize(
    'task, condition',
    [
        pytest.param('a', 'succeeded', id='a'),
        pytest.param('b', 'succeeded or failed', id='b'),
        pytest.param('c', '(succeeded and x)', id='c'),
        pytest.param('d', 'succeeded', id='d'),
        pytest.param('e', '(succeeded and x and y and z)', id='e'),
        pytest.param('f', '(x and succeeded) or failed', id='f'),
        pytest.param('g', 'succeeded or expired', id='h'),
        pytest.param('h', 'succeeded or failed or expired', id='h'),
        pytest.param('i', '(submitted and succeeded) or expired', id='i'),
        pytest.param('j', 'succeeded or submit_failed or expired', id='j'),
        pytest.param('k', 'succeeded or failed or submit_failed', id='k'),
        pytest.param(
            'l', 'succeeded or failed or submit_failed or expired', id='l'
        ),
    ],
)
async def test_implicit_completion_expression(
    implicit_completion_config,
    task,
    condition,
):
    """It should generate a completion expression from the graph.

    If no completion expression is provided in the runtime section, then it
    should auto generate one inferring whether outputs are required or not from
    the graph.
    """
    completion_expression = get_completion_expression(
        implicit_completion_config.taskdefs[task]
    )
    assert completion_expression == condition


async def test_clock_expire_partially_satisfied_task(
    flow,
    scheduler,
    start,
):
    """Clock expire should take effect on a partially satisfied task.

    Tests proposal point 8:
    https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2000',
            'runahead limit': 'P0',
            'special tasks': {
                'clock-expire': 'e',
            },
            'graph': {
                'P1D': '''
                    # this prerequisite we will satisfy
                    a => e

                    # this prerequisite we will leave unsatisfied creating a
                    # partially-satisfied task
                    b => e
                '''
            },
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        # satisfy one of the prerequisites
        a = schd.pool.get_task(ISO8601Point('20000101T0000Z'), 'a')
        assert a
        schd.pool.spawn_on_output(a, TASK_OUTPUT_SUCCEEDED)

        # the task "e" should now be spawned
        e = schd.pool.get_task(ISO8601Point('20000101T0000Z'), 'e')
        assert e

        # check for clock-expired tasks
        schd.pool.clock_expire_tasks()

        # the task should now be in the expired state
        assert e.state(TASK_STATUS_EXPIRED)
