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

import contextlib
import os
import sqlite3
import unittest
from unittest import mock
from tempfile import mktemp

import pytest

from cylc.flow.rundb import CylcWorkflowDAO


GLOBAL_CONFIG = """
[platforms]
    [[desktop[0-9]{2}|laptop[0-9]{2}]]
        # hosts = platform name (default)
        # Note: "desktop01" and "desktop02" are both valid and distinct
        # platforms
    [[sugar]]
        hosts = localhost
        job runner = slurm
    [[hpc]]
        hosts = hpcl1, hpcl2
        retrieve job logs = True
        job runner = pbs
    [[hpcl1-bg]]
        hosts = hpcl1
        retrieve job logs = True
        job runner = background
    [[hpcl2-bg]]
        hosts = hpcl2
        retrieve job logs = True
        job runner = background
"""


class TestRunDb(unittest.TestCase):

    def setUp(self):
        self.dao = CylcWorkflowDAO(':memory:')
        self.mocked_connection = mock.Mock()
        self.dao.connect = mock.MagicMock(return_value=self.mocked_connection)

    get_select_task_job = [
        ["cycle", "name", "NN"],
        ["cycle", "name", None],
        ["cycle", "name", "02"],
    ]

    def test_select_task_job(self):
        """Test the rundb CylcWorkflowDAO select_task_job method"""
        columns = self.dao.tables[CylcWorkflowDAO.TABLE_TASK_JOBS].columns[3:]
        expected_values = [[2 for _ in columns]]

        self.mocked_connection.execute.return_value = expected_values

        # parameterized test
        for cycle, name, submit_num in self.get_select_task_job:
            returned_values = self.dao.select_task_job(cycle, name, submit_num)

            for column in columns:
                self.assertEqual(2, returned_values[column.name])

    def test_select_task_job_sqlite_error(self):
        """Test when the rundb CylcWorkflowDAO select_task_job method raises
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
            r'''
                CREATE TABLE foo (
                    bar,
                    baz,
                    pub
                )
            '''
        )
        conn.execute(
            r'''
                INSERT INTO foo
                VALUES (?,?,?)
            ''',
            ['BAR', 'BAZ', 'PUB']
        )
        conn.commit()
        conn.close()

        dao = CylcWorkflowDAO(temp_db)
        dao.remove_columns('foo', ['bar', 'baz'])

        conn = dao.connect()
        data = list(conn.execute(r'SELECT * from foo'))
        assert data == [('PUB',)]


def test_operational_error(monkeypatch, tmp_path, caplog):
    """Test logging on operational error."""
    # create a db object
    db_file = tmp_path / 'db'
    dao = CylcWorkflowDAO(db_file)

    # stage some stuff
    dao.add_delete_item(CylcWorkflowDAO.TABLE_TASK_JOBS)
    dao.add_insert_item(CylcWorkflowDAO.TABLE_TASK_JOBS, ['pub'])
    dao.add_update_item(CylcWorkflowDAO.TABLE_TASK_JOBS, ['pub'])

    # connect the to DB
    dao.connect()

    # then delete the file - this will result in an OperationalError
    db_file.unlink()

    # execute & commit the staged items
    with pytest.raises(sqlite3.OperationalError):
        dao.execute_queued_items()

    # ensure that the failed transaction is logged for debug purposes
    assert len(caplog.messages) == 1
    message = caplog.messages[0]
    assert 'An error occurred when writing to the database' in message
    assert 'DELETE FROM task_jobs' in message
    assert 'INSERT OR REPLACE INTO task_jobs' in message
    assert 'UPDATE task_jobs' in message
