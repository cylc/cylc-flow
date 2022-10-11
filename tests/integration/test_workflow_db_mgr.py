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
import sqlite3

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


def remove_is_manual_submit_col(schd: Scheduler) -> None:
    """Remove is_manual_submit from task_states table of scheduler's DB."""

    pri_dao = schd.workflow_db_mgr.get_pri_dao()
    conn = pri_dao.connect()

    # Get current task_states table column names, minus "is_manual_submit".
    cursor = conn.execute('PRAGMA table_info(task_states)')
    desc = cursor.fetchall()
    c_names = ','.join(
        [fields[1] for fields in desc if fields[1] != "is_manual_submit"]
    )

    # Replace the table (without the column) and reset cylc_version to 8.0.2.
    # Note "ALTER TABLE 'x' DROP COLUMN 'y'" is not supported yet.
    conn.execute(rf'CREATE TABLE "tmp"({c_names})')
    conn.execute(
        rf'INSERT INTO "tmp"({c_names}) SELECT {c_names} FROM "task_states"')
    conn.execute(r'DROP TABLE "task_states"')
    conn.execute(r'ALTER TABLE "tmp" RENAME TO "task_states"')
    conn.commit()
    pri_dao.close()


def fake_cylc_version(schd: Scheduler, ver: str) -> None:
    pri_dao = schd.workflow_db_mgr.get_pri_dao()
    conn = pri_dao.connect()
    conn.execute(
        rf'UPDATE "workflow_params" SET "value" = "{ver}" '
        r'WHERE "key" = "cylc_version"')
    conn.commit()
    pri_dao.close()


async def test_db_upgrade_pre_803(
    flow, one_conf, start, scheduler, log_filter, db_select
):
    """Test restart with upgrade of pre-8.0.3 DB.

    8.0.3 added the "is_manual_submit" column to the task_states table.
    """
    reg = flow(one_conf)

    # Run a scheduler to create a DB.
    schd: Scheduler = scheduler(reg, paused_start=True)
    async with start(schd):
        assert ('n_restart', '0') in db_select(schd, False, 'workflow_params')

    remove_is_manual_submit_col(schd)

    schd: Scheduler = scheduler(reg, paused_start=True)
    with pytest.raises(sqlite3.OperationalError):
        async with start(schd):
            assert (
                ('n_restart', '1') in db_select(schd, False, 'workflow_params')
            )

    fake_cylc_version(schd, "8.0.2")

    schd: Scheduler = scheduler(reg, paused_start=True)
    async with start(schd):
        assert ('n_restart', '2') in db_select(schd, False, 'workflow_params')
