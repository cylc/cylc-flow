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

"""Compatibility tests for handling old workflow databases."""

from functools import partial
from unittest.mock import Mock
import pytest
import sqlite3

from cylc.flow.exceptions import CylcError, ServiceFileError
from cylc.flow.task_pool import TaskPool
from cylc.flow.workflow_db_mgr import (
    CylcWorkflowDAO,
    WorkflowDatabaseManager,
)
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker


@pytest.fixture
def _setup_db(tmp_path):
    """Fixture to create old DB."""
    def _inner(values, db_file_name='sql.db'):
        db_file = tmp_path / db_file_name
        db_file.parent.mkdir(parents=True, exist_ok=True)
        # Note: cannot use CylcWorkflowDAO here as creating outdated DB
        conn = sqlite3.connect(str(db_file))
        conn.execute((
            r'CREATE TABLE task_states(name TEXT, cycle TEXT, flow_nums TEXT,'
            r' time_created TEXT, time_updated TEXT, submit_num INTEGER,'
            r' status TEXT, flow_wait INTEGER, is_manual_submit INTEGER,'
            r' PRIMARY KEY(name, cycle, flow_nums));')
        )
        conn.execute((
            r'CREATE TABLE task_jobs(cycle TEXT, name TEXT,'
            r' submit_num INTEGER, is_manual_submit INTEGER,'
            r' try_num INTEGER, time_submit TEXT, time_submit_exit TEXT,'
            r' submit_status INTEGER, time_run TEXT, time_run_exit TEXT,'
            r' run_signal TEXT, run_status INTEGER, platform_name TEXT,'
            r' job_runner_name TEXT, job_id TEXT,'
            r' PRIMARY KEY(cycle, name, submit_num));'
        ))
        for value in values:
            conn.execute(value)
        conn.execute((
            r"INSERT INTO task_jobs VALUES"
            r"    ('10090101T0000Z', 'foo', 1, 0, 1, '2022-12-05T14:46:06Z',"
            r" '2022-12-05T14:46:07Z', 0, '2022-12-05T14:46:10Z',"
            r" '2022-12-05T14:46:39Z', '', 0, 'localhost', 'background',"
            r" 4377)"
        ))
        conn.commit()
        conn.close()
        return db_file
    return _inner


def test_upgrade_pre_810_fails_on_multiple_flows(_setup_db):
    values = [(
        r'INSERT INTO task_states VALUES'
        r"    ('foo', '10050101T0000Z', '[1, 3]',"
        r" '2022-12-05T14:46:33Z',"
        r" '2022-12-05T14:46:40Z', 1, 'succeeded', 0, 0)"
    )]
    db_file_name = _setup_db(values)
    with CylcWorkflowDAO(db_file_name) as dao, pytest.raises(
        CylcError,
        match='^Cannot .* 8.0.x to 8.1.0 .* used.$'
    ):
        WorkflowDatabaseManager.upgrade_pre_810(dao)


def test_upgrade_pre_810_pass_on_single_flow(_setup_db):
    values = [(
        r'INSERT INTO task_states VALUES'
        r"    ('foo', '10050101T0000Z', '[1]',"
        r" '2022-12-05T14:46:33Z',"
        r" '2022-12-05T14:46:40Z', 1, 'succeeded', 0, 0)"
    )]
    db_file_name = _setup_db(values)
    with CylcWorkflowDAO(db_file_name) as dao:
        WorkflowDatabaseManager.upgrade_pre_810(dao)
        result = dao.connect().execute(
            'SELECT DISTINCT flow_nums FROM task_jobs;'
        ).fetchall()[0][0]
    assert result == '[1]'


def test_check_workflow_db_compat(_setup_db, capsys):
    """method can pick private or public db to check.
    """
    # Create public and private databases with different cylc versions:
    create = r'CREATE TABLE workflow_params(key TEXT, value TEXT)'
    insert = (
        r'INSERT INTO workflow_params VALUES'
        r'("cylc_version", "{}")'
    )
    pri_path = _setup_db(
        [create, insert.format('7.99.99')], db_file_name='private/db')
    pub_path = _setup_db(
        [create, insert.format('7.99.98')], db_file_name='public/db')

    with pytest.raises(ServiceFileError, match='99.98'):
        WorkflowDatabaseManager.check_db_compatibility(pub_path)

    with pytest.raises(ServiceFileError, match='99.99'):
        WorkflowDatabaseManager.check_db_compatibility(pri_path)


def test_cylc_7_db_wflow_params_table(_setup_db):
    """Test back-compat needed by workflow state xtrigger for Cylc 7 DBs."""
    ptformat = "CCYY"
    create = r'CREATE TABLE suite_params(key TEXT, value TEXT)'
    insert = (
        r'INSERT INTO suite_params VALUES'
        rf'("cycle_point_format", "{ptformat}")'
    )
    db_file_name = _setup_db([create, insert])
    with CylcWorkflowDBChecker('foo', 'bar', db_path=db_file_name) as checker:
        with pytest.raises(
            sqlite3.OperationalError, match="no such table: workflow_params"
        ):
            checker._get_db_point_format()

        assert checker.db_point_fmt == ptformat


def test_pre_830_task_action_timers(_setup_db):
    """Test back compat for task_action_timers table.

    Before 8.3.0, TaskEventMailContext had an extra field "ctx_type" at
    index 1. TaskPool.load_db_task_action_timers() should be able to
    discard this field.
    """
    values = [
        r'''
            CREATE TABLE task_action_timers(
                cycle TEXT, name TEXT, ctx_key TEXT, ctx TEXT, delays TEXT,
                num INTEGER, delay TEXT, timeout TEXT,
                PRIMARY KEY(cycle, name, ctx_key)
            );
        ''',
        r'''
            INSERT INTO task_action_timers VALUES(
                '1','foo','[["event-mail", "failed"], 9]',
                '["TaskEventMailContext", ["event-mail", "event-mail", "notifications@fbc.gov", "jfaden"]]',
                '[0.0]',1,'0.0','1709229449.61275'
            );
        ''',
        r'''
            INSERT INTO task_action_timers VALUES(
                '1','foo','["try_timers", "execution-retry"]', null,
                '[94608000.0]',1,NULL,NULL
            );
        ''',
    ]
    db_file = _setup_db(values)
    mock_pool = Mock()
    load_db_task_action_timers = partial(
        TaskPool.load_db_task_action_timers, mock_pool
    )
    with CylcWorkflowDAO(db_file, create_tables=True) as dao:
        dao.select_task_action_timers(load_db_task_action_timers)
