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

import logging
import pytest

from cylc.flow.commands import (
    run_cmd,
    force_trigger_tasks
)
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.id import TaskTokens, Tokens
from cylc.flow.network.resolvers import TaskMsg
from cylc.flow.task_events_mgr import (
    TaskEventsManager,
)
from cylc.flow.task_outputs import (
    TASK_OUTPUTS,
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
    TASK_OUTPUT_SUCCEEDED,
    get_completion_expression,
)
from cylc.flow.task_state import (
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_WAITING,
)

if TYPE_CHECKING:
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.scheduler import Scheduler


OPT_BOTH_ERR = "Output {} can't be both required and optional"


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
                {TaskTokens('1', 'a')},
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
                {TaskTokens('1', 'a')},
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
            schd.release_tasks_to_run()

        # NOTE: The submit number isn't presently incremented via this code
        # pathway so we have to hack it here. If the task messages in this test
        # get ignored because of some future change, then you can safely remove
        # this line (it's not what this test is testing).
        a_1.submit_num += 1

        # tell the scheduler that the task *submit-failed*
        schd.message_queue.put(
            TaskMsg(
                Tokens('//1/a/01'),
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
                Tokens('//1/a/01'),
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
                Tokens('//1/a/01'),
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
                'outputs': {x: f'{x * 3}' for x in 'abcdefghijklxyz'}
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


async def test_clock_expiry(
    flow,
    scheduler,
    start,
):
    """Waiting tasks should be considered for clock-expiry.

    Tests two things:

    * Manually triggered tasks should not be considered for clock-expiry.

      Tests proposal point 10:
      https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal

    * Active tasks should not be considered for clock-expiry.

      Closes https://github.com/cylc/cylc-flow/issues/6025
    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2000',
            'runahead limit': 'P1',
            'special tasks': {
                'clock-expire': 'x'
            },
            'graph': {
                'P1Y': 'x'
            },
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        # the first task (waiting)
        one = schd.pool.get_task(ISO8601Point('20000101T0000Z'), 'x')
        assert one

        # the second task (preparing)
        two = schd.pool.get_task(ISO8601Point('20010101T0000Z'), 'x')
        assert two
        two.state_reset(TASK_STATUS_PREPARING)

        # the third task (force-triggered)
        await run_cmd(force_trigger_tasks(schd, ['20100101T0000Z/x'], ['1']))
        three = schd.pool.get_task(ISO8601Point('20100101T0000Z'), 'x')
        assert three

        # check for expiry
        schd.pool.clock_expire_tasks()

        # the first task should be expired (it was waiting)
        assert one.state(TASK_STATUS_EXPIRED)
        assert one.state.outputs.is_message_complete(TASK_OUTPUT_EXPIRED)

        # the second task should *not* be expired (it was active)
        assert not two.state(TASK_STATUS_EXPIRED)
        assert not two.state.outputs.is_message_complete(TASK_OUTPUT_EXPIRED)

        # the third task should *not* be expired (it was a manual submit)
        assert not three.state(TASK_STATUS_EXPIRED)
        assert not three.state.outputs.is_message_complete(TASK_OUTPUT_EXPIRED)


async def test_removed_taskdef(
    flow,
    scheduler,
    start,
):
    """It should handle tasks being removed from the config.

    If the config of an active task is removed from the config by restart /
    reload, then we must provide a fallback completion expression, otherwise
    the expression will be blank (task has no required or optional outputs).

    The fallback is to consider the outputs complete if *any* final output is
    received. Since the task has been removed from the workflow its outputs
    should be inconsequential.

    See: https://github.com/cylc/cylc-flow/issues/5057
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a & z'
            }
        }
    })

    # start the workflow and mark the tasks as running
    schd: 'Scheduler' = scheduler(id_)
    async with start(schd):
        for itask in schd.pool.get_tasks():
            itask.state_reset(TASK_STATUS_RUNNING)
            assert itask.state.outputs._completion_expression == 'succeeded'

    # remove the task "z" from the config
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a'
            }
        }
    }, workflow_id=id_)

    # restart the workflow
    schd: 'Scheduler' = scheduler(id_)
    async with start(schd):
        # 1/a:
        # * is still in the config
        # * is should still have a sensible completion expression
        # * its outputs should be incomplete if the task fails
        a_1 = schd.pool.get_task(IntegerPoint('1'), 'a')
        assert a_1
        assert a_1.state.outputs._completion_expression == 'succeeded'
        a_1.state.outputs.set_message_complete(TASK_OUTPUT_FAILED)
        assert not a_1.is_complete()

        # 1/z:
        # * is no longer in the config
        # * should have a blank completion expression
        # * its outputs should be completed by any final output
        z_1 = schd.pool.get_task(IntegerPoint('1'), 'z')
        assert z_1
        assert z_1.state.outputs._completion_expression == ''
        z_1.state.outputs.set_message_complete(TASK_OUTPUT_FAILED)
        assert z_1.is_complete()


@pytest.mark.parametrize(
    'graph, err',
    [
        pytest.param(
            """
            a
            a?
            """,
            OPT_BOTH_ERR.format("a:succeeded"),
            id='1',
        ),
        pytest.param(
            """
            a => b
            a?
            """,
            OPT_BOTH_ERR.format("a:succeeded"),
            id='2',
        ),
        pytest.param(
            """
            a? => b
            a
            """,
            OPT_BOTH_ERR.format("a:succeeded"),
            id='3',
        ),
        pytest.param(
            """
            a => b?
            b
            """,
            OPT_BOTH_ERR.format("b:succeeded"),
            id='4',
        ),
        pytest.param(
            """
            a => b:succeeded
            b?
            """,
            OPT_BOTH_ERR.format("b:succeeded"),
            id='5',
        ),
        pytest.param(
            """
            a => b:succeeded
            c => b?
            """,
            OPT_BOTH_ERR.format("b:succeeded"),
            id='6',
        ),
        pytest.param(
            """
            c:x => d
            a => c:x?
            """,
            OPT_BOTH_ERR.format("c:x"),
            id='7',
        ),
        pytest.param(
            """
            c:x? => d
            a => c:x
            """,
            OPT_BOTH_ERR.format("c:x"),
            id='8',
        ),
        pytest.param(
            """
            FAM:finish-all?
            """,
            "Family pseudo-output FAM:finish-all can't be optional",
            id='9',
        ),
        pytest.param(
            """
            a => b => c
            b?
            """,
            OPT_BOTH_ERR.format("b:succeeded"),
            id='10',
        ),
        pytest.param(
            """
            a => FAM => c
            """,
            "Family trigger required: FAM => c",
            id='11',
        ),
    ],
)
async def test_optional_outputs_consistency(flow, validate, graph, err):
    """Check that inconsistent output optionality fails validation."""
    id_ = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': graph
                },
            },
            'runtime': {
                'FAM': {},
                'm1, m2': {
                    'inherit': 'FAM',
                },
                'c': {
                    'outputs': {
                        'x': 'x',
                    },
                },
            },
        },
    )
    with pytest.raises(WorkflowConfigError) as exc_ctx:
        validate(id_)
    assert err in str(exc_ctx.value)


@pytest.mark.parametrize(
    'graph, expected',
    [
        pytest.param(
            "a => b",
            {
                ("a", "succeeded"): True,  # inferred
                ("b", "succeeded"): True,  # default
                ("a", "failed"): None,  # (not set)
                ("b", "failed"): None,  # (not set)
            },
            id='0',
        ),
        pytest.param(
            """
            a => b
            b?
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("b", "succeeded"): False,  # inferred
                ("b", "failed"): None,  # (not set)
            },
            id='1',
        ),
        pytest.param(
            """
            a:failed => b
            """,
            {
                ("a", "failed"): True,
                ("b", "succeeded"): True,
                ("a", "succeeded"): None,
                ("b", "failed"): None,
            },
            id='2',
        ),
        pytest.param(
            """
            a => b
            b
            """,
            {
                ("a", "succeeded"): True,
                ("b", "succeeded"): True,
            },
            id='3',
        ),
        pytest.param(
            """
            a => b
            b?
            """,
            {
                ("a", "succeeded"): True,
                ("b", "succeeded"): False,
            },
            id='4',
        ),
        pytest.param(
            """
            a? => b
            """,
            {
                ("a", "succeeded"): False,
                ("b", "succeeded"): True,
            },
            id='5',
        ),
        pytest.param(
            """
            a? => b
            b?
            """,
            {
                ("a", "succeeded"): False,
                ("b", "succeeded"): False,
            },
            id='6',
        ),
        pytest.param(
            """
            a? => b?
            """,
            {
                ("a", "succeeded"): False,
                ("b", "succeeded"): False,
            },
            id='7',
        ),
        pytest.param(
            """
            FAM
            """,
            {
                ("m1", "succeeded"): True,  # family default
                ("m2", "succeeded"): True,  # family default
            },
            id='8_a',
        ),
        pytest.param(
            """
            FAM:succeed-all?
            """,
            {
                ("m1", "succeeded"): False,  # family default
                ("m2", "succeeded"): False,  # family default
            },
            id='8_b',
        ),
        pytest.param(
            """
            FAM
            m1?
            """,
            {
                ("m1", "succeeded"): False,  # inferred
                ("m2", "succeeded"): True,  # family default
            },
            id='8_c',
        ),
        pytest.param(
            """
            a => FAM
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("m1", "succeeded"): True,  # default
                ("m2", "succeeded"): True,  # default
            },
            id='8',
        ),
        pytest.param(
            """
            a => FAM
            m2?
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("m1", "succeeded"): True,  # default
                ("m2", "succeeded"): False,  # inferred (override default)
            },
            id='9',
        ),
        pytest.param(
            """
            a => FAM:finish-all
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("m1", "succeeded"): False,  # family default
                ("m2", "succeeded"): False,  # family default
            },
            id='10',
        ),
        pytest.param(
            """
            FAM:succeed-any => a
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("m1", "succeeded"): True,  # family default
                ("m2", "succeeded"): True,  # family default
            },
            id='11',
        ),
        pytest.param(
            """
            FAM:succeed-any? => a
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("m1", "succeeded"): False,  # family default
                ("m2", "succeeded"): False,  # family default
            },
            id='11a',
        ),
        pytest.param(
            """
            FAM:succeed-any => a
            m1?
            """,
            {
                ("a", "succeeded"): True,
                ("m1", "succeeded"): False,
                ("m2", "succeeded"): True,
            },
            id='12',
        ),
        pytest.param(
            """
            a & b? => c
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("b", "succeeded"): False,  # inferred
                ("c", "succeeded"): True,  # default
            },
            id='13',
        ),
        pytest.param(
            """
            a => c:x
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("c", "succeeded"): True,  # default
                ("c", "x"): True,  # inferred
            },
            id='14',
        ),
        pytest.param(
            """
            a => c:x?
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("c", "succeeded"): True,  # default
                ("c", "x"): False,  # inferred
            },
            id='15',
        ),
        pytest.param(
            """
            a => b => c  # infer :succeeded for b inside chain
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("b", "succeeded"): True,  # inferred
                ("c", "succeeded"): True,  # default
            },
            id='16',
        ),
        pytest.param(
            # Check we don't infer c:succeeded at end-of-chain
            # when there's an & at the end.
            """
            a => b & c
            c?
            """,
            {
                ("a", "succeeded"): True,  # inferred
                ("b", "succeeded"): True,  # default
                ("c", "succeeded"): False,  # inferred
            },
            id='17',
        ),
    ],
)
async def test_optional_outputs_inference(
    flow, validate, graph, expected
):
    """Check task output optionality after graph parsing.

    This checks taskdef.outputs, which holds inferred and default values.

    """
    id = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': graph
                },
            },
            'runtime': {
                'FAM': {},
                'm1, m2': {
                    'inherit': 'FAM',
                },
                'c': {
                    'outputs': {
                        'x': 'x',
                    },
                },
            },
        }
    )
    config = validate(id)
    for (task, output), exp in expected.items():
        tdef = config.get_taskdef(task)
        (_, required) = tdef.outputs[output]
        assert required == exp


async def test_log_outputs(flow, validate, caplog):
    """Test logging of optional and required outputs inferred from the graph.

    This probes output optionality inferred by the graph parser, so it does
    not include RHS-only tasks that just default to :succeeded required.

    """
    id = flow(
        {
            'scheduling': {
                'graph': {
                    'R1': """
                        # (b:succeeded required by default, not by inference)
                        a? => FAM:succeed-all? => b
                        m1
                        a? => c:x?
                        a? => c:y
                     """,
                },
            },
            'runtime': {
                'FAM': {},
                'm1, m2': {
                    'inherit': 'FAM',
                },
                'c': {
                    "outputs": {
                        "x": "x",
                        "y": "y"
                    }
                }
            }
        }
    )
    caplog.set_level(logging.DEBUG)
    validate(id)

    found_opt = False
    found_req = False

    for record in caplog.records:
        msg = record.message
        if "Optional outputs inferred from the graph:" in msg:
            found_opt = True
            for output in ["a:succeeded", "m2:succeeded", "c:x"]:
                assert output in msg
            for output in [
                "b:succeeded", "m1:succeeded", "c:y", "c:succeeded"
            ]:
                assert output not in msg
        elif "Required outputs inferred from the graph:" in msg:
            found_req = True
            for output in ["m1:succeeded", "c:y"]:
                assert output in msg
            for output in [
                "m2:succeeded", "b:succeeded", "a:succeeded", "c:x",
                "c:succeeded"
            ]:
                assert output not in msg

    assert found_opt
    assert found_req
