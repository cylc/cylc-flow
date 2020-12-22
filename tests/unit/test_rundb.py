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

        dao = CylcSuiteDAO(temp_db)
        dao.remove_columns('foo', ['bar', 'baz'])

        conn = dao.connect()
        data = [row for row in conn.execute(r'SELECT * from foo')]
        assert data == [('PUB',)]


if __name__ == '__main__':
    unittest.main()
