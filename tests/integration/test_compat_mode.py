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

"""Tests for Cylc 7 compatibility mode."""

from typing import TYPE_CHECKING

from cylc.flow.cycling.integer import IntegerPoint
from cylc.flow.data_store_mgr import TASK_PROXIES

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


async def test_blocked_tasks_in_n0(flow, scheduler, run, complete):
    """Ensure that tasks with no satisfied dependencies remain in the pool.

    In this example, the "recover" task is not satisfiable because its upstream
    dependency "foo:failed" will never be satisfied. The unsatisfiable
    "recover" task should remain in n=0 until removed/completed.

    See https://github.com/cylc/cylc-flow/issues/4983
    """
    id_ = flow(
        {
            'scheduling': {
                'initial cycle point': '1',
                'cycling mode': 'integer',
                'runahead limit': 'P2',
                'dependencies': {
                    'P1': {
                        'graph': '''
                            foo:fail => recover
                            foo | recover => bar
                        ''',
                    },
                },
            },
        },
        filename='suite.rc',
    )
    schd: 'Scheduler' = scheduler(id_, paused_start=False, debug=True)
    async with run(schd):
        # the workflow should run for three cycles, then runahead stall
        await complete(schd, *(f'{cycle}/bar' for cycle in range(1, 4)))
        assert schd.is_stalled

        # the "blocked" recover tasks should remain in the pool
        assert {t.identity for t in schd.pool.get_tasks()} == {
            '1/recover',
            '2/recover',
            '3/recover',
            '4/foo',
        }

        # the "blocked" tasks should remain visible in the data store
        assert {
            (x.cycle_point, x.graph_depth, x.name)
            for x in schd.data_store_mgr.data[schd.tokens.id][
                TASK_PROXIES
            ].values()
        } == {
            ('1', 1, 'foo'),
            ('1', 0, 'recover'),
            ('1', 1, 'bar'),
            ('2', 1, 'foo'),
            ('2', 0, 'recover'),
            ('2', 1, 'bar'),
            ('3', 1, 'foo'),
            ('3', 0, 'recover'),
            ('3', 1, 'bar'),
            ('4', 0, 'foo'),
            ('4', 1, 'recover'),
            ('4', 1, 'bar'),
        }

        # remove the unsatisfiable tasks
        # (i.e. manually implement a suicide trigger)
        for cycle in range(1, 4):
            itask = schd.pool.get_task(IntegerPoint(str(cycle)), 'recover')
            schd.pool.remove(itask, 'suicide-trigger')
        assert {t.identity for t in schd.pool.get_tasks()} == {
            '4/foo',
            '5/foo',
            '6/foo',
            '7/foo',
        }

        # the workflow continue into the next three cycles, then stall again
        # (i.e. the runahead limit should move forward after the removes)
        await complete(schd, *(f'{cycle}/bar' for cycle in range(4, 7)))
        assert schd.is_stalled

        assert {
            (x.cycle_point, x.graph_depth, x.name)
            for x in schd.data_store_mgr.data[schd.tokens.id][
                TASK_PROXIES
            ].values()
        } == {
            ('4', 1, 'foo'),
            ('4', 0, 'recover'),
            ('4', 1, 'bar'),
            ('5', 1, 'foo'),
            ('5', 0, 'recover'),
            ('5', 1, 'bar'),
            ('6', 1, 'foo'),
            ('6', 0, 'recover'),
            ('6', 1, 'bar'),
            ('7', 0, 'foo'),
            ('7', 1, 'recover'),
            ('7', 1, 'bar'),
        }
