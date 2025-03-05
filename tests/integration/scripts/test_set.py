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

"""Test "cylc set" functionality.

Note: see also functional tests
"""

from secrets import token_hex

from cylc.flow.commands import (
    run_cmd,
    set_prereqs_and_outputs,
)
from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.data_messages_pb2 import PbTaskProxy
from cylc.flow.data_store_mgr import TASK_PROXIES
from cylc.flow.flow_mgr import FLOW_ALL
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_outputs import (
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.task_state import (
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)


def outputs_section(*names: str) -> dict:
    """Create outputs section with random messages for the given output names.
    """
    return {
        'outputs': {
            name: token_hex() for name in names
        }
    }


async def test_set_parentless_spawning(
    flow,
    scheduler,
    run,
    complete,
):
    """Ensure that setting outputs does not interfere with parentless spawning.

    Setting outputs manually causes the logic to follow a different code
    pathway to "natural" output satisfaction. If we're not careful this could
    lead to "premature shutdown" (i.e. the scheduler thinks it's finished when
    it isn't), this test makes sure that's not the case.
    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'runahead limit': 'P0',
            'graph': {'P1': 'a => z'},
        },
    })
    schd: Scheduler = scheduler(id_, paused_start=False)
    async with run(schd):
        # mark cycle 1 as succeeded
        schd.pool.set_prereqs_and_outputs(
            ['1/a', '1/z'], ['succeeded'], None, ['1']
        )

        # the parentless task "a" should be spawned out to the runahead limit
        assert schd.pool.get_task_ids() == {'2/a', '3/a'}

        # the workflow should run on to the next cycle
        await complete(schd, '2/a', timeout=5)


async def test_rerun_incomplete(
    flow,
    scheduler,
    run,
    complete,
    reflog,
):
    """Incomplete tasks should be re-run."""
    id_ = flow({
        'scheduling': {
            'graph': {'R1': 'a => z'},
        },
        'runtime': {
            # register a custom output
            'a': {'outputs': {'x': 'xyz'}},
        },
    })
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # generate 1/a:x but do not complete 1/a
        schd.pool.set_prereqs_and_outputs(['1/a'], ['x'], None, ['1'])
        triggers = reflog(schd)
        await complete(schd)

    assert triggers == {
        # the task 1/a should have been run despite the earlier
        # setting of the "x" output
        ('1/a', None),
        ('1/z', ('1/a',)),
    }


async def test_data_store(
    flow,
    scheduler,
    start,
):
    """Test that manually set prereqs/outputs are applied to the data store."""
    id_ = flow({
        'scheduling': {
            'graph': {'R1': 'a => z'},
        },
        'runtime': {
            # register a custom output
            'a': {'outputs': {'x': 'xyz'}},
        },
    })
    schd: Scheduler = scheduler(id_)
    async with start(schd):
        await schd.update_data_structure()
        data = schd.data_store_mgr.data[schd.tokens.id]
        task_a: PbTaskProxy = data[TASK_PROXIES][
            schd.pool.get_task(IntegerPoint('1'), 'a').tokens.id
        ]

        # set the 1/a:succeeded prereq of 1/z
        schd.pool.set_prereqs_and_outputs(
            ['1/z'], None, ['1/a:succeeded'], ['1'])
        task_z = data[TASK_PROXIES][
            schd.pool.get_task(IntegerPoint('1'), 'z').tokens.id
        ]
        await schd.update_data_structure()
        assert task_z.prerequisites[0].satisfied is True

        # set 1/a:x the task should be waiting with output x satisfied
        schd.pool.set_prereqs_and_outputs(['1/a'], ['x'], None, ['1'])
        await schd.update_data_structure()
        assert task_a.state == TASK_STATUS_WAITING
        assert task_a.outputs['x'].satisfied is True
        assert task_a.outputs['succeeded'].satisfied is False

        # set 1/a:succeeded the task should be succeeded with output x sat
        schd.pool.set_prereqs_and_outputs(['1/a'], ['succeeded'], None, ['1'])
        await schd.update_data_structure()
        assert task_a.state == TASK_STATUS_SUCCEEDED
        assert task_a.outputs['x'].satisfied is True
        assert task_a.outputs['succeeded'].satisfied is True


async def test_incomplete_detection(
    one_conf,
    flow,
    scheduler,
    start,
    log_filter,
):
    """It should detect and log finished tasks left with incomplete outputs."""
    schd = scheduler(flow(one_conf))
    async with start(schd):
        schd.pool.set_prereqs_and_outputs(['1/one'], ['failed'], None, ['1'])
    assert log_filter(contains='1/one did not complete')


async def test_pre_all(flow, scheduler, run):
    """Ensure that --pre=all is interpreted as a special case
    and _not_ tokenized.
    """
    id_ = flow({'scheduling': {'graph': {'R1': 'a => z'}}})
    schd = scheduler(id_, paused_start=False)
    async with run(schd) as log:
        schd.pool.set_prereqs_and_outputs(['1/z'], [], ['all'], ['all'])
        warn_or_higher = [i for i in log.records if i.levelno > 30]
        assert warn_or_higher == []


async def test_no_outputs_given(flow, scheduler, start):
    """Test `cylc set` without providing any outputs.

    It should set the "success pathway" outputs.
    """
    schd: Scheduler = scheduler(
        flow({
            'scheduling': {
                'graph': {
                    'R1': r"""
                        foo? => alpha
                        foo:submitted? => bravo
                        foo:started? => charlie
                        foo:x => xray
                        # Optional custom outputs not emitted:
                        foo:y? => yankee
                        # Non-success-pathway outputs not emitted:
                        foo:submit-failed? => delta
                    """,
                },
            },
            'runtime': {
                'foo': outputs_section('x', 'y'),
            },
        })
    )
    async with start(schd):
        foo = schd.pool.get_tasks()[0]
        await run_cmd(
            set_prereqs_and_outputs(schd, [foo.identity], [FLOW_ALL])
        )
        assert set(foo.state.outputs.get_completed_outputs()) == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
            TASK_OUTPUT_SUCCEEDED,
            'x'
        }
        assert schd.pool.get_task_ids() == {
            '1/alpha',
            '1/bravo',
            '1/charlie',
            '1/xray',
        }


async def test_completion_expr(flow, scheduler, start):
    """Test `cylc set` without providing any outputs on a task that has a
    custom completion expression."""
    conf = {
        'scheduling': {
            'graph': {
                'R1': 'foo? | foo:x? => bar'
            },
        },
        'runtime': {
            'foo': {
                **outputs_section('x'),
                'completion': '(succeeded or x) or failed'
            },
        },
    }
    schd: Scheduler = scheduler(flow(conf))
    async with start(schd):
        foo = schd.pool.get_tasks()[0]
        await run_cmd(
            set_prereqs_and_outputs(schd, [foo.identity], [FLOW_ALL])
        )
        assert set(foo.state.outputs.get_completed_outputs()) == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
            TASK_OUTPUT_SUCCEEDED,
        }
