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

"""Test set, trigger, and remove command back-compat with --flow=all.

This option is now just the default (flows = ['all'] -> []).

BACK COMPAT: handle --flow=all from pre-8.5 clients
"""

import pytest

from cylc.flow.commands import (
    force_trigger_tasks,
    remove_tasks,
    run_cmd,
    set_prereqs_and_outputs,
)
from cylc.flow.exceptions import InputError
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_outputs import TASK_OUTPUT_SUCCEEDED


async def test_back_compat_flow_all(flow, scheduler, start):
    """blah"""
    conf = {
        'scheduling': {
            'graph': {
                'R1': 'a & b'
            },
        },
    }
    schd: Scheduler = scheduler(flow(conf))
    async with start(schd):
        foo, bar = schd.pool.get_tasks()

        # set should fail with an illegal flow value (allx)
        with pytest.raises(
            InputError,
            match="Flow values must be integers, or 'new', or 'none'"
        ):
            await run_cmd(
                set_prereqs_and_outputs(schd, [foo.identity], ['allx'])
            )
        # but OK with --flow=all
        await run_cmd(
            set_prereqs_and_outputs(schd, [foo.identity], ['all'])
        )
        assert TASK_OUTPUT_SUCCEEDED in foo.state.outputs.get_completed_outputs()

        # trigger should fail with an illegal flow value (allx)
        with pytest.raises(
            InputError,
            match="Flow values must be integers, or 'new', or 'none'"
        ):
            await run_cmd(
                force_trigger_tasks(schd, [bar.identity], ['allx'])
            )
        # but OK with --flow=all
        await run_cmd(
            force_trigger_tasks(schd, [bar.identity], ['all'])
        )
        assert bar in schd.pool.tasks_to_trigger_now

        # remove should fail with an illegal flow value (allx)
        with pytest.raises(
            InputError,
            match="Flow values must be integers"
        ):
            await run_cmd(
                remove_tasks(schd, [bar.identity], ['allx'])
            )
        # but OK with --flow=all
        await run_cmd(
            remove_tasks(schd, [bar.identity], ['all'])
        )
        assert bar not in schd.pool.get_tasks()
        assert bar not in schd.pool.tasks_to_trigger_now
