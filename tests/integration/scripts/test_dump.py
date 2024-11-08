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

"""Test the "cylc dump" command."""

from cylc.flow.option_parsers import (
    Options,
)
from cylc.flow.scripts.dump import (
    dump,
    get_option_parser,
)

DumpOptions = Options(get_option_parser())


async def test_dump_tasks(flow, scheduler, start):
    """It should show n=0 tasks.

    See: https://github.com/cylc/cylc-flow/pull/5600
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'true',
        },
        'scheduling': {
            'graph': {
                'R1': 'a => b => c',
            },
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        # schd.release_queued_tasks()
        await schd.update_data_structure()
        ret = []
        await dump(
            id_,
            DumpOptions(disp_form='tasks', legacy_format=True),
            write=ret.append
        )
        assert ret == ['a, 1, waiting, not-held, queued, not-runahead']


async def test_dump_format(flow, scheduler, start):
    """Check the new "cylc dump" output format, i.e. task IDs.

    See: https://github.com/cylc/cylc-flow/pull/6440
    """
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'true',
        },
        'scheduling': {
            'graph': {
                'R1': 'a',
            },
        },
    })
    schd = scheduler(id_)
    async with start(schd):
        [itask] = schd.pool.get_tasks()

        itask.state_reset(is_held=True)
        schd.pool.data_store_mgr.delta_task_held(itask)

        itask.state_reset(is_runahead=True)
        schd.pool.data_store_mgr.delta_task_runahead(itask)

        itask.state_reset(is_queued=True)
        schd.pool.data_store_mgr.delta_task_queued(itask)

        itask.flow_nums = set([1,2])
        schd.pool.data_store_mgr.delta_task_flow_nums(itask)

        await schd.update_data_structure()
        ret = []
        await dump(
            id_,
            DumpOptions(disp_form='tasks', show_flows=True),
            write=ret.append
        )
        assert ret == [
            '1/a:waiting (held,queued,runahead) flows=[1,2]',
        ]
