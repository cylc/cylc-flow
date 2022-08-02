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

from cylc.flow.scheduler import Scheduler


async def test_restart_number(
    flow, one_conf, start, scheduler, log_filter, db_select
):
    """The restart number should increment correctly."""
    reg = flow(one_conf)

    async def test(expected_restart_num: int, do_reload: bool = False):
        """(Re)start the workflow and check the restart number is as expected.
        """
        schd: Scheduler = scheduler(reg, paused_start=True)
        async with start(schd) as log:
            if do_reload:
                schd.command_reload_workflow()
            assert schd.workflow_db_mgr.n_restart == expected_restart_num
            assert log_filter(
                log, contains=f"(re)start number={expected_restart_num + 1}"
                # (In the log, it's 1 higher than backend value)
            )
        assert ('n_restart', f'{expected_restart_num}') in db_select(
            schd, False, 'workflow_params'
        )

    # First start
    await test(expected_restart_num=0)
    # Restart
    await test(expected_restart_num=1)
    # Restart + reload - https://github.com/cylc/cylc-flow/issues/4918
    await test(expected_restart_num=2, do_reload=True)
    # Final restart
    await test(expected_restart_num=3)
