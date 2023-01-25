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

"""
Tests for worklfow_db_manager
"""

import pytest
import sqlite3

from cylc.flow.exceptions import CylcError, ServiceFileError
from cylc.flow.workflow_db_mgr import (
    CylcWorkflowDAO,
    WorkflowDatabaseManager,
)


@pytest.fixture
def _setup_db(tmp_path):
    def _inner(values, db_file_name='sql.db'):
        db_file = tmp_path / db_file_name
        db_file.parent.mkdir(parents=True, exist_ok=True)
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
        return db_file
    return _inner


def test_upgrade_pre_810_fails_on_multiple_flows(_setup_db):
    values = [(
        r'INSERT INTO task_states VALUES'
        r"    ('foo', '10050101T0000Z', '[1, 3]',"
        r" '2022-12-05T14:46:33Z',"
        r" '2022-12-05T14:46:40Z', 1, 'succeeded', 0, 0)"
    ),]
    db_file_name = _setup_db(values)
    pri_dao = CylcWorkflowDAO(db_file_name)
    with pytest.raises(
        CylcError,
        match='^Cannot .* 8.0.x to 8.1.0 .* used.$'
    ):
        WorkflowDatabaseManager.upgrade_pre_810(pri_dao)


def test_upgrade_pre_810_pass_on_single_flow(_setup_db):
    values = [(
        r'INSERT INTO task_states VALUES'
        r"    ('foo', '10050101T0000Z', '[1]',"
        r" '2022-12-05T14:46:33Z',"
        r" '2022-12-05T14:46:40Z', 1, 'succeeded', 0, 0)"
    ),]
    db_file_name = _setup_db(values)
    pri_dao = CylcWorkflowDAO(db_file_name)
    WorkflowDatabaseManager.upgrade_pre_810(pri_dao)
    conn = sqlite3.connect(db_file_name)
    result = conn.execute(
        'SELECT DISTINCT flow_nums FROM task_jobs;').fetchall()[0][0]
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

    # Setup workflow DB manager:
    db_mgr = WorkflowDatabaseManager(
        pub_d=str(pub_path.parent), pri_d=str(pri_path.parent))

    with pytest.raises(ServiceFileError, match='99.98'):
        db_mgr.check_workflow_db_compatibility(use_pri_dao=False)

    with pytest.raises(ServiceFileError, match='99.99'):
        db_mgr.check_workflow_db_compatibility()
