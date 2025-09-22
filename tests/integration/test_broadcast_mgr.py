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

"""Tests for Broadcast Manager."""

import asyncio

import pytest

from cylc.flow import commands
from cylc.flow.cycling.integer import IntegerInterval, IntegerPoint
from cylc.flow.cycling.iso8601 import ISO8601Interval, ISO8601Point
from cylc.flow.task_state import TASK_STATUS_FAILED


async def test_reject_valid_broadcast_is_remote_clash_with_config(
    one_conf, flow, start, scheduler, log_filter
):
    """`put_broadcast` gracefully rejects invalid broadcast:

    Existing config = [task][remote]host = foo
    Broadcast       = [task]platform = bar

    https://github.com/cylc/cylc-flow/issues/6693
    """
    one_conf.update({'runtime': {'root': {'platform': 'foo'}}})
    wid = flow(one_conf)
    schd = scheduler(wid)
    async with start(schd):
        bc_mgr = schd.broadcast_mgr
        good, bad = bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'remote': {'host': 'bar'}}]
        )

        # the error should be reported in the workflow log
        assert log_filter(contains='Cannot apply broadcast')
        assert bc_mgr.broadcasts == {'1': {}}

        # the bad setting should be reported
        assert good == []
        assert bad == {
            'settings': [
                {'remote': {'host': 'bar'}},
            ]
        }


async def test_reject_valid_broadcast_is_remote_clash_with_broadcast(
    one_conf, flow, start, scheduler, log_filter
):
    """`put_broadcast` gracefully rejects invalid broadcast:

    Existing Broadcast = [task][remote]host = foo
    New Broadcast      = [task]platform = bar

    https://github.com/cylc/cylc-flow/pull/6711/files#r2033457964
    """
    schd = scheduler(flow(one_conf))
    async with start(schd):
        bc_mgr = schd.broadcast_mgr
        _, bad = bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'remote': {'host': 'bar'}}]
        )
        assert bad == {}  # broadcast should be successful

        # this should not be allowed, if it is the scheduler will crash
        # when unpaused:
        good, bad = bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'platform': 'foo'}]
        )

        # the error should be reported in the workflow log
        assert log_filter(contains='Cannot apply broadcast')
        assert bc_mgr.broadcasts == {'1': {'one': {'remote': {'host': 'bar'}}}}

        # the bad setting should be reported
        assert good == []
        assert bad == {
            'settings': [
                {'platform': 'foo'},
            ]
        }


@pytest.mark.parametrize('cycling_mode', ('integer', 'gregorian', '360_day'))
async def test_broadcast_expire_limit(
    cycling_mode,
    flow,
    scheduler,
    run,
    complete,
    capcall,
):
    """Test automatic broadcast expiry.

    To prevent broadcasts from piling up and causing a memory leak, we expire
    (aka clear) them.

    The broadcast expiry limit is the oldest active cycle MINUS the longest
    cycling sequence.

    See https://github.com/cylc/cylc-flow/pull/6964
    """
    # capture broadcast expiry calls
    _expires = capcall('cylc.flow.broadcast_mgr.BroadcastMgr.expire_broadcast')

    def expires():
        """Return a list of the cycle limit expired since the last call."""
        ret = [x[0][1] for x in _expires]
        _expires.clear()
        return ret

    def cycle(number):
        """Return a cycle point object in the relevant format."""
        if cycling_mode == 'integer':
            return IntegerPoint(str(number))
        else:
            return ISO8601Point(f'000{number}')

    def interval(number):
        """Return an integer object in the relevant format."""
        if cycling_mode == 'integer':
            return IntegerInterval(sequence(number))
        else:
            return ISO8601Interval(sequence(number))

    def sequence(number):
        """Return a sequence string in the relevant format."""
        if cycling_mode == 'integer':
            return f'P{number}'
        else:
            return f'P{number}Y'

    # a workflow with a sequential task
    id_ = flow({
        'scheduler': {
            'cycle point format': 'CCYY'
        } if cycling_mode != 'integer' else {},

        'scheduling': {
            'cycling mode': cycling_mode,
            'initial cycle point': cycle(1),
            'graph': {
                # the sequence with the sequential task
                sequence(1): f'a[-{sequence(1)}] => a',
                # a longer sequence to make the offset more interesting
                sequence(3): 'a',
            }
        }
    })
    schd = scheduler(id_, paused_start=False)

    async with run(schd):
        # the longest cycling sequence has a step of "3"
        assert schd.config.interval_of_longest_sequence == interval(3)

        # no broadcast expires should happen on startup
        assert expires() == []

        # when a cycle closes, auto broadcast expiry should happen
        # NOTE: datetimes cannot be negative, so this expiry will be skipped
        # for datetimetime cycling workflows
        await complete(schd, f'{cycle(1)}/a')
        assert expires() in ([], [cycle(-1)])

        await complete(schd, f'{cycle(2)}/a')
        assert expires() == [cycle(0)]

        await complete(schd, f'{cycle(3)}/a')
        assert expires() == [cycle(1)]


async def test_broadcast_expiry_async(
    one_conf, flow, scheduler, run, complete, capcall
):
    """Test auto broadcast expiry with async workflows.

    Auto broadcast expiry should not happen in async workflows as there is only
    one cycle so it doesn't make sense.

    See https://github.com/cylc/cylc-flow/pull/6964
    """
    # capture broadcast expiry calls
    expires = capcall('cylc.flow.broadcast_mgr.BroadcastMgr.expire_broadcast')

    id_ = flow(one_conf)
    schd = scheduler(id_, paused_start=False)

    async with run(schd):
        # this is an async workflow so the longest cycling interval is a
        # null interval
        assert (
            schd.config.interval_of_longest_sequence
            == IntegerInterval.get_null()
        )
        await complete(schd)

    # no auto-expiry should take place
    assert expires == []


async def test_broadcast_old_cycle(flow, scheduler, run, complete):
    """It should not expire broadcasts whilst the scheduler is paused.

    This tests the use case of broadcasting to a historical cycle (whilst the
    workflow is paused) before triggering it to run to ensure that the
    broadcast is not expired before the operator is able to run the trigger
    command.

    For context, see https://github.com/cylc/cylc-flow/pull/6499 and
    https://github.com/cylc/cylc-flow/pull/6192#issuecomment-2486785465
    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'graph': {
                'P1': 'a[-P1] => a',
            },
        },
    })
    schd = scheduler(id_, paused_start=False)
    async with run(schd):
        # issue a broadcast into the first cycle
        schd.broadcast_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['a'],
            settings=[{'environment': {'ANSWER': '42'}}]
        )
        assert list(schd.broadcast_mgr.broadcasts) == ['1']

        # the broadcast should expire after the workflow passes cycle "3"
        await complete(schd, '3/a')
        assert list(schd.broadcast_mgr.broadcasts) == []

        # pause the workflow
        await commands.run_cmd(commands.pause(schd))

        # issue a broadcast into the first cycle (now behind the broadcast
        # expire point)
        schd.broadcast_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['a'],
            settings=[{'simulation': {'fail cycle points': '1'}}]
        )

        # this should not be expired whilst the scheduler is paused
        await schd._main_loop()  # run one iteration of the main loop
        assert list(schd.broadcast_mgr.broadcasts) == ['1']

        # trigger the first cycle and resume the workflow
        await commands.run_cmd(commands.force_trigger_tasks(schd, ['1'], []))
        await commands.run_cmd(commands.resume(schd))

        # the broadcast should still be there
        await schd._main_loop()  # run one iteration of the main loop
        assert list(schd.broadcast_mgr.broadcasts) == ['1']

        # and should take effect
        a_1 = schd.pool._get_task_by_id('1/a')
        async with asyncio.timeout(5):
            while True:
                await asyncio.sleep(0.1)
                if a_1.state(TASK_STATUS_FAILED):
                    break
