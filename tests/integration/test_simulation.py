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
from queue import Queue
from types import SimpleNamespace

from cylc.flow.cycling.iso8601 import ISO8601Point
from cylc.flow.simulation import sim_time_check


def get_msg_queue_item(queue, id_):
    for item in queue.queue:
        if id_ in str(item.job_id):
            return item


@pytest.fixture(scope='module')
async def sim_time_check_setup(
    mod_flow, mod_scheduler, mod_start, mod_one_conf
):
    schd = mod_scheduler(mod_flow({
        'scheduler': {'cycle point format': '%Y'},
        'scheduling': {
            'initial cycle point': '1066',
            'graph': {
                'R1': 'one & fail_all & fast_forward'
            }
        },
        'runtime': {
            'one': {},
            'fail_all': {
                'simulation': {'fail cycle points': 'all'},
                'outputs': {'foo': 'bar'}
            },
            # This task ought not be finished quickly, but for the speed up
            'fast_forward': {
                'execution time limit': 'PT1M',
                'simulation': {'speedup factor': 2}
            }
        }
    }))
    msg_q = Queue()
    async with mod_start(schd):
        itasks = schd.pool.get_tasks()
        for i in itasks:
            i.try_timers = {'execution-retry': SimpleNamespace(num=0)}
        yield schd, itasks, msg_q


def test_false_if_not_running(sim_time_check_setup, monkeypatch):
    schd, itasks, msg_q = sim_time_check_setup

    # False if task status not running:
    assert sim_time_check(msg_q, itasks) is False


def test_sim_time_check_sets_started_time(sim_time_check_setup):
    """But sim_time_check still returns False"""
    schd, _, msg_q = sim_time_check_setup
    one_1066 = schd.pool.get_task(ISO8601Point('1066'), 'one')
    one_1066.state.status = 'running'
    assert one_1066.summary['started_time'] is None
    assert sim_time_check(msg_q, [one_1066]) is False
    assert one_1066.summary['started_time'] is not None


def test_task_finishes(sim_time_check_setup, monkeypatch):
    """...and an appropriate message sent.

    Checks all possible outcomes in sim_time_check where elapsed time is
    greater than the simulation time.

    Does NOT check every possible cause on an outcome - this is done
    in unit tests.
    """
    schd, _, msg_q = sim_time_check_setup
    monkeypatch.setattr('cylc.flow.simulation.time', lambda: 0)

    # Setup a task to fail
    fail_all_1066 = schd.pool.get_task(ISO8601Point('1066'), 'fail_all')
    fail_all_1066.state.status = 'running'
    fail_all_1066.try_timers = {'execution-retry': SimpleNamespace(num=0)}

    # Before simulation time is up:
    assert sim_time_check(msg_q, [fail_all_1066]) is False

    # After simulation time is up:
    monkeypatch.setattr('cylc.flow.simulation.time', lambda: 12)
    assert sim_time_check(msg_q, [fail_all_1066]) is True
    assert get_msg_queue_item(msg_q, '1066/fail_all').message == 'failed'

    # Succeeds and records messages for all outputs:
    fail_all_1066.try_timers = {'execution-retry': SimpleNamespace(num=1)}
    msg_q = Queue()
    assert sim_time_check(msg_q, [fail_all_1066]) is True
    assert sorted(i.message for i in msg_q.queue) == ['bar', 'succeeded']


def test_task_sped_up(sim_time_check_setup, monkeypatch):
    """Task will speed up by a factor set in config."""
    schd, _, msg_q = sim_time_check_setup
    fast_forward_1066 = schd.pool.get_task(
        ISO8601Point('1066'), 'fast_forward')
    fast_forward_1066.state.status = 'running'

    monkeypatch.setattr('cylc.flow.simulation.time', lambda: 0)
    assert sim_time_check(msg_q, [fast_forward_1066]) is False
    monkeypatch.setattr('cylc.flow.simulation.time', lambda: 29)
    assert sim_time_check(msg_q, [fast_forward_1066]) is False
    monkeypatch.setattr('cylc.flow.simulation.time', lambda: 31)
    assert sim_time_check(msg_q, [fast_forward_1066]) is True
