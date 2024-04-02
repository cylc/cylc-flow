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

from pathlib import Path
import pytest
import sqlite3
from typing import Callable
from unittest.mock import Mock
from shutil import copytree, rmtree

from cylc.flow.exceptions import InputError
from cylc.flow.pathutil import get_cylc_run_dir
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.xtriggers.workflow_state import workflow_state
from ..conftest import MonkeyMock

def test_inferred_run(tmp_run_dir: Callable, monkeymock: MonkeyMock):
    """Test that the workflow_state xtrigger infers the run number"""
    id_ = 'isildur'
    expected_workflow_id = f'{id_}/run1'
    cylc_run_dir = str(tmp_run_dir())
    tmp_run_dir(expected_workflow_id, installed=True, named=True)
    mock_db_checker = monkeymock(
        'cylc.flow.xtriggers.workflow_state.CylcWorkflowDBChecker',
        return_value=Mock(
            get_remote_point_format=lambda: 'CCYY',
        )
    )

    _, results = workflow_state(id_, task='precious', point='3000')
    mock_db_checker.assert_called_once_with(cylc_run_dir, expected_workflow_id)
    assert results['workflow'] == expected_workflow_id


    # Now test we can see workflows in alternate cylc-run directories
    # e.g. for `cylc workflow-state` or xtriggers targetting another user.
    alt_cylc_run_dir = cylc_run_dir + "_alt"

    # copy the cylc-run dir to alt location and delete the original.
    copytree(cylc_run_dir, alt_cylc_run_dir, symlinks=True)
    rmtree(cylc_run_dir)

    # It can no longer parse IDs in the original cylc-run location.
    with pytest.raises(InputError):
        _, results = workflow_state(id_, task='precious', point='3000')

    # But it can via an explicit alternate run directory.
    mock_db_checker.reset_mock()
    _, results = workflow_state(id_, task='precious', point='3000', cylc_run_dir=alt_cylc_run_dir)
    mock_db_checker.assert_called_once_with(alt_cylc_run_dir, expected_workflow_id)
    assert results['workflow'] == expected_workflow_id

def test_back_compat(tmp_run_dir):
    """Test workflow_state xtrigger backwards compatibility with Cylc 7
    database."""
    id_ = 'celebrimbor'
    c7_run_dir: Path = tmp_run_dir(id_)
    (c7_run_dir / WorkflowFiles.FLOW_FILE).rename(
        c7_run_dir / WorkflowFiles.SUITE_RC
    )
    db_file = c7_run_dir / 'log' / 'db'
    db_file.parent.mkdir(exist_ok=True)
    # Note: cannot use CylcWorkflowDAO here as creating outdated DB
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute(r"""
            CREATE TABLE suite_params(key TEXT, value TEXT, PRIMARY KEY(key));
        """)
        conn.execute(r"""
            CREATE TABLE task_states(
                name TEXT, cycle TEXT, time_created TEXT, time_updated TEXT,
                submit_num INTEGER, status TEXT, PRIMARY KEY(name, cycle)
            );
        """)
        conn.executemany(
            r'INSERT INTO "suite_params" VALUES(?,?);',
            [('cylc_version', '7.8.12'),
             ('cycle_point_format', '%Y'),
             ('cycle_point_tz', 'Z')]
        )
        conn.execute(r"""
           INSERT INTO "task_states" VALUES(
               'mithril','2012','2023-01-30T18:19:15Z','2023-01-30T18:19:15Z',
               0,'succeeded'
            );
        """)
        conn.commit()
    finally:
        conn.close()

    satisfied, _ = workflow_state(id_, task='mithril', point='2012')
    assert satisfied
    satisfied, _ = workflow_state(id_, task='arkenstone', point='2012')
    assert not satisfied
