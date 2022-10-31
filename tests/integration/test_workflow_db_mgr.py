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

from pkg_resources import parse_version

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


def db_remove_column(schd: Scheduler, table: str, column: str) -> None:
    """Remove a column from a scheduler DB table.

    ALTER TABLE DROP COLUMN is not supported by sqlite yet, so we have to copy
    the table (without the column) and rename it back to the original.
    """
    with schd.workflow_db_mgr.get_pri_dao() as pri_dao:
        conn = pri_dao.connect()
        # Get current column names, minus column
        cursor = conn.execute(f'PRAGMA table_info({table})')
        desc = cursor.fetchall()
        c_names = ','.join(
            [fields[1] for fields in desc if fields[1] != column]
        )
        # Copy table data to a temporary table, and rename it back.
        conn.execute(rf'CREATE TABLE "tmp"({c_names})')
        conn.execute(
            rf'INSERT INTO "tmp"({c_names}) SELECT {c_names} FROM {table}')
        conn.execute(rf'DROP TABLE "{table}"')
        conn.execute(rf'ALTER TABLE "tmp" RENAME TO "{table}"')
        conn.commit()


def upgrade_db_from_version(schd, version):
    """Runs the DB upgrader from the specified version.

    Args:
        schd:
            The Scheduler who's DB you want to upgrade.
        version:
            The version you want to upgrade from.
            (i.e. what version do you want to tell Cylc the workflow ran
            with last time).

    """
    with schd.workflow_db_mgr.get_pri_dao() as pri_dao:
        schd.workflow_db_mgr.upgrade(parse_version(version), pri_dao)


async def test_db_upgrade_pre_803(
    flow, one_conf, start, scheduler, log_filter, db_select
):
    """Test scheduler restart with upgrade of pre-8.0.3 DB."""
    reg = flow(one_conf)

    # Run a scheduler to create a DB.
    schd: Scheduler = scheduler(reg, paused_start=True)
    async with start(schd):
        assert ('n_restart', '0') in db_select(schd, False, 'workflow_params')

    # Remove task_states:is_manual_submit to fake a pre-8.0.3 DB.
    db_remove_column(schd, "task_states", "is_manual_submit")

    schd: Scheduler = scheduler(reg, paused_start=True)

    # Run the DB upgrader for version 8.0.3
    # (8.0.3 does not require upgrade so should be skipped)
    upgrade_db_from_version(schd, '8.0.3')

    # Restart should fail due to the missing column.
    with pytest.raises(sqlite3.OperationalError):
        async with start(schd):
            pass
    assert ('n_restart', '1') in db_select(schd, False, 'workflow_params')

    schd: Scheduler = scheduler(reg, paused_start=True)

    # Run the DB upgrader for version 8.0.2
    # (8.0.2 requires upgrade)
    upgrade_db_from_version(schd, '8.0.2')
    # Restart should now succeed.
    async with start(schd):
        assert ('n_restart', '2') in db_select(schd, False, 'workflow_params')
