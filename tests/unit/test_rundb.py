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
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import (
    List,
    Optional,
    Tuple,
)
import unittest
from unittest import mock

import pytest

from cylc.flow.exceptions import PlatformLookupError
from cylc.flow.flow_mgr import FlowNums
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.util import serialise_set


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
    conn = sqlite3.connect(':memory:')
    yield conn
    conn.close()  # doesn't raise error on re-invocation


def test_operational_error(tmp_path, caplog):
    """Test logging on operational error."""
    # create a db object
    db_file = tmp_path / 'db'
    with CylcWorkflowDAO(db_file) as dao:
        # stage some stuff
        dao.add_delete_item(CylcWorkflowDAO.TABLE_TASK_JOBS)
        dao.add_insert_item(CylcWorkflowDAO.TABLE_TASK_JOBS, ['pub'])
        dao.add_update_item(
            CylcWorkflowDAO.TABLE_TASK_JOBS, ({'pub': None}, {})
        )

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


def test_table_creation(tmp_path: Path):
    """Test tables are NOT created by default."""
    db_file = tmp_path / 'db'
    stmt = "SELECT name FROM sqlite_master WHERE type='table'"
    with CylcWorkflowDAO(db_file) as dao:
        tables = list(dao.connect().execute(stmt))
    assert tables == []
    with CylcWorkflowDAO(db_file, create_tables=True) as dao:
        tables = [i[0] for i in dao.connect().execute(stmt)]
    assert CylcWorkflowDAO.TABLE_WORKFLOW_PARAMS in tables


def test_context_manager_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Test connection is closed even if an exception occurs somewhere."""
    db_file = tmp_path / 'db'
    mock_close = mock.Mock()
    with monkeypatch.context() as mp:
        mp.setattr(CylcWorkflowDAO, 'close', mock_close)
        with CylcWorkflowDAO(db_file) as dao, pytest.raises(RuntimeError):
            mock_close.assert_not_called()
            raise RuntimeError('mock err')
        mock_close.assert_called_once()
    # Close connection for real:
    dao.close()


def test_select_task_pool_for_restart_if_not_platforms(tmp_path):
    """Returns error if platform error or errors raised by callback.
    """
    # Setup a fake callback function which returns the fake "platform_name":
    def callback(index, row):
        return ''.join(row)

    db_file = tmp_path / 'db'
    dao = CylcWorkflowDAO(db_file, create_tables=True)
    # Fiddle the connect method to return a list of fake "platform_names":
    dao.connect = lambda: SimpleNamespace(execute=lambda _: ['foo', 'bar'])

    # Assert that an error is raised and that it mentions both fake platforms:
    with pytest.raises(
        PlatformLookupError,
        match='not defined.*\n.*foo.*\n.*bar'
    ):
        dao.select_task_pool_for_restart(callback)


@pytest.mark.parametrize(
    'values, expected',
    [
        pytest.param(
            [
                ({1, 2}, '2021-01-01T00:00:00'),
                ({3, 4}, '2021-01-01T00:00:02'),
                ({5, 6}, '2021-01-01T00:00:01'),
            ],
            {3, 4},
            id="basic"
        ),
        pytest.param(
            [
                ({2}, '2021-01-01T00:00:00'),
                (set(), '2021-01-01T00:00:01'),
                (set(), '2021-01-01T00:00:02'),
            ],
            {2},
            id="ignore flow=none"
        ),
        pytest.param(
            [
                (set(), '2021-01-01T00:00:01'),
                (set(), '2021-01-01T00:00:02'),
            ],
            None,
            id="all flow=none"
        ),
    ],
)
def test_select_latest_flow_nums(
    values: List[Tuple[FlowNums, str]], expected: Optional[FlowNums]
):
    with CylcWorkflowDAO(':memory:') as dao:
        conn = dao.connect()
        conn.execute(
            "CREATE TABLE task_states (flow_nums TEXT, time_created TEXT)"
        )
        for (fnums, timestamp) in values:
            conn.execute(
                "INSERT INTO task_states VALUES ("
                f"{json.dumps(serialise_set(fnums))}, {json.dumps(timestamp)}"
                ")"
            )
        conn.commit()

        assert dao.select_latest_flow_nums() == expected
