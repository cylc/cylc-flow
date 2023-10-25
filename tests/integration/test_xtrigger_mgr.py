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
"""Tests for the behaviour of xtrigger manager.
"""


async def test_2_xtriggers(flow, start, scheduler, monkeypatch):
    """Test that if an itask has 2 wall_clock triggers with different
    offsets that xtrigger manager gets both of them.

    https://github.com/cylc/cylc-flow/issues/5783

    n.b. Clock 3 exists to check the memoization path is followed,
    and causing this test to give greater coverage.
    """
    task_point = 1588636800                # 2020-05-05
    ten_years_ahead = 1904169600           # 2030-05-05
    monkeypatch.setattr(
        'cylc.flow.xtriggers.wall_clock.time',
        lambda: ten_years_ahead - 1
    )
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'initial cycle point': '2020-05-05',
            'xtriggers': {
                'clock_1': 'wall_clock()',
                'clock_2': 'wall_clock(offset=P10Y)',
                'clock_3': 'wall_clock(offset=P10Y)',
            },
            'graph': {
                'R1': '@clock_1 & @clock_2 & @clock_3 => foo'
            }
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        foo_proxy = schd.pool.get_tasks()[0]
        clock_1_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_1')
        clock_2_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_2')
        clock_3_ctx = schd.xtrigger_mgr.get_xtrig_ctx(foo_proxy, 'clock_2')

        assert clock_1_ctx.func_kwargs['trigger_time'] == task_point
        assert clock_2_ctx.func_kwargs['trigger_time'] == ten_years_ahead
        assert clock_3_ctx.func_kwargs['trigger_time'] == ten_years_ahead

        schd.xtrigger_mgr.call_xtriggers_async(foo_proxy)
        assert foo_proxy.state.xtriggers == {
            'clock_1': True,
            'clock_2': False,
            'clock_3': False,
        }
