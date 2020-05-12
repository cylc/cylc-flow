# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

import contextlib
import os
import sqlite3
import unittest

from tempfile import mktemp
from unittest import mock

from cylc.flow.rundb import CylcSuiteDAO


GLOBALRC = """
[job platforms]
    [[desktop[0-9]{2}|laptop[0-9]{2}]]
        # hosts = platform name (default)
        # Note: "desktop01" and "desktop02" are both valid and distinct
        # platforms
    [[sugar]]
        remote hosts = localhost
        batch system = slurm
    [[hpc]]
        remote hosts = hpcl1, hpcl2
        retrieve job logs = True
        batch system = pbs
    [[hpcl1-bg]]
        remote hosts = hpcl1
        retrieve job logs = True
        batch system = background
    [[hpcl2-bg]]
        remote hosts = hpcl2
        retrieve job logs = True
        batch system = background
"""


class TestRunDb(unittest.TestCase):

    def setUp(self):
        self.dao = CylcSuiteDAO(':memory:')
        self.mocked_connection = mock.Mock()
        self.dao.connect = mock.MagicMock(return_value=self.mocked_connection)

    get_select_task_job = [
        ["cycle", "name", "NN"],
        ["cycle", "name", None],
        ["cycle", "name", "02"],
    ]

    def test_select_task_job(self):
        """Test the rundb CylcSuiteDAO select_task_job method"""
        columns = self.dao.tables[CylcSuiteDAO.TABLE_TASK_JOBS].columns[3:]
        expected_values = [[2 for _ in columns]]

        self.mocked_connection.execute.return_value = expected_values

        # parameterized test
        for cycle, name, submit_num in self.get_select_task_job:
            returned_values = self.dao.select_task_job(cycle, name, submit_num)

            for column in columns:
                self.assertEqual(2, returned_values[column.name])

    def test_select_task_job_sqlite_error(self):
        """Test that when the rundb CylcSuiteDAO select_task_job method raises
        a SQLite exception, the method returns None"""

        self.mocked_connection.execute.side_effect = sqlite3.DatabaseError

        r = self.dao.select_task_job("it'll", "raise", "an error!")
        self.assertIsNone(r)


@contextlib.contextmanager
def create_temp_db():
    """Create and tidy a temporary database for testing purposes."""
    temp_db = mktemp()
    conn = sqlite3.connect(temp_db)
    yield (temp_db, conn)
    os.remove(temp_db)
    conn.close()  # doesn't raise error on re-invocation


def test_remove_columns():
    """Test workaround for dropping columns in sqlite3."""
    with create_temp_db() as (temp_db, conn):
        conn.execute(
            rf'''
                CREATE TABLE foo (
                    bar,
                    baz,
                    pub
                )
            '''
        )
        conn.execute(
            rf'''
                INSERT INTO foo
                VALUES (?,?,?)
            ''',
            ['BAR', 'BAZ', 'PUB']
        )
        conn.commit()
        conn.close()

        dao = CylcSuiteDAO(temp_db)
        dao.remove_columns('foo', ['bar', 'baz'])

        conn = dao.connect()
        data = [row for row in conn.execute(rf'SELECT * from foo')]
        assert data == [('PUB',)]


def test_upgrade_hold_swap():
    """Pre Cylc8 DB upgrade compatibility test."""
    # test data
    initial_data = [
        # (name, cycle, status, hold_swap)
        ('foo', '1', 'waiting', ''),
        ('bar', '1', 'held', 'waiting'),
        ('baz', '1', 'held', 'running'),
        ('pub', '1', 'waiting', 'held')
    ]
    expected_data = [
        # (name, cycle, status, hold_swap, is_held)
        ('foo', '1', 'waiting', 0),
        ('bar', '1', 'waiting', 1),
        ('baz', '1', 'running', 1),
        ('pub', '1', 'waiting', 1)
    ]
    tables = [
        CylcSuiteDAO.TABLE_TASK_POOL,
        CylcSuiteDAO.TABLE_TASK_POOL_CHECKPOINTS
    ]

    with create_temp_db() as (temp_db, conn):
        # initialise tables
        for table in tables:
            conn.execute(
                rf'''
                    CREATE TABLE {table} (
                        name varchar(255),
                        cycle varchar(255),
                        status varchar(255),
                        hold_swap varchar(255)
                    )
                '''
            )

            conn.executemany(
                rf'''
                    INSERT INTO {table}
                    VALUES (?,?,?,?)
                ''',
                initial_data
            )

        # close database
        conn.commit()
        conn.close()

        # open database as cylc dao
        dao = CylcSuiteDAO(temp_db)
        conn = dao.connect()

        # check the initial data was correctly inserted
        for table in tables:
            dump = [x for x in conn.execute(rf'SELECT * FROM {table}')]
            assert dump == initial_data

        # upgrade
        assert dao.upgrade_is_held()

        # check the data was correctly upgraded
        for table in tables:
            dump = [x for x in conn.execute(rf'SELECT * FROM task_pool')]
            assert dump == expected_data

        # make sure the upgrade is skipped on future runs
        assert not dao.upgrade_is_held()


def test_upgrade_to_platforms(mock_glbl_cfg):
    """Test upgrader logic for platforms in the database.
    """
    # Set up the globalrc
    mock_glbl_cfg('cylc.flow.rundb.glbl_cfg', GLOBALRC)

    # task name, cycle, user_at_host, batch_system
    initial_data = [
        ('hpc_with_pbs', '1', 'hpcl1', 'pbs'),
        ('desktop_with_bg', '1', 'desktop01', 'background'),
        ('slurm_no_host', '1', '', 'slurm'),
        ('hpc_bg', '1', 'hpcl1', 'background'),
        ('username_given', '1', 'slartibartfast@hpcl1', 'pbs')
    ]
    # task name, cycle, user, platform
    expected_data = [
        ('hpc_with_pbs', '1', '', 'hpc'),
        ('desktop_with_bg', '1', '', 'desktop01'),
        ('slurm_no_host', '1', '', 'sugar'),
        ('hpc_bg', '1', '', 'hpcl1-bg'),
        ('username_given', '1', 'slartibartfast', 'hpc'),
    ]
    with create_temp_db() as (temp_db, conn):
        conn.execute(
            rf'''
                CREATE TABLE {CylcSuiteDAO.TABLE_TASK_JOBS} (
                    name varchar(255),
                    cycle varchar(255),
                    user_at_host varchar(255),
                    batch_system varchar(255)
                )
            '''
        )
        conn.executemany(
            rf'''
                INSERT INTO {CylcSuiteDAO.TABLE_TASK_JOBS}
                VALUES (?,?,?,?)
            ''',
            initial_data
        )
        # close database
        conn.commit()
        conn.close()

        # open database as cylc dao
        dao = CylcSuiteDAO(temp_db)
        conn = dao.connect()

        # check the initial data was correctly inserted
        dump = [
            x for x in conn.execute(
                rf'SELECT * FROM {CylcSuiteDAO.TABLE_TASK_JOBS}'
            )
        ]
        assert dump == initial_data

        # Upgrade function returns True?
        assert dao.upgrade_to_platforms()

        # check the data was correctly upgraded
        dump = [
            x for x in conn.execute(
                rf'SELECT name, cycle, user, platform_name FROM task_jobs'
            )
        ]
        assert dump == expected_data

        # make sure the upgrade is skipped on future runs
        assert not dao.upgrade_to_platforms()


if __name__ == '__main__':
    unittest.main()
