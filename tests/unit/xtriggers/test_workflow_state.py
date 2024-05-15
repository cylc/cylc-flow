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

import sqlite3
from typing import TYPE_CHECKING
from shutil import copytree, rmtree

from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.xtriggers.workflow_state import workflow_state

if TYPE_CHECKING:
    from typing import Callable
    from pytest import CaptureFixture
    from pathlib import Path


def test_inferred_run(tmp_run_dir: 'Callable', capsys: 'CaptureFixture'):
    """Test that the workflow_state xtrigger infers the run number.

    Method: the faked run-dir has no DB to connect to, but the WorkflowPoller
    prints inferred ID to stderr if the run-dir exists.

    """
    id_ = 'isildur'
    expected_workflow_id = f'{id_}/run1'
    cylc_run_dir = str(tmp_run_dir())
    tmp_run_dir(expected_workflow_id, installed=True, named=True)
    workflow_state(id_ + '//3000/precious')
    assert expected_workflow_id in capsys.readouterr().err

    # Now test we can see workflows in alternate cylc-run directories
    # e.g. for `cylc workflow-state` or xtriggers targetting another user.
    alt_cylc_run_dir = cylc_run_dir + "_alt"

    # copy the cylc-run dir to alt location and delete the original.
    copytree(cylc_run_dir, alt_cylc_run_dir, symlinks=True)
    rmtree(cylc_run_dir)

    # It can no longer parse IDs in the original cylc-run location.
    workflow_state(id_)
    assert expected_workflow_id not in capsys.readouterr().err

    # But it can via an explicit alternate run directory.
    workflow_state(id_, alt_cylc_run_dir=alt_cylc_run_dir)
    assert expected_workflow_id in capsys.readouterr().err


def test_back_compat(tmp_run_dir: 'Callable', caplog: 'CaptureFixture'):
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

    # Test workflow_state function
    satisfied, _ = workflow_state(id_ + '//2012/mithril')
    assert satisfied
    satisfied, _ = workflow_state(id_ + '//2012/arkenstone')
    assert not satisfied

    # Test back-compat (old suite_state function)
    from cylc.flow.xtriggers.suite_state import suite_state
    satisfied, _ = suite_state(suite=id_, task='mithril', point='2012')
    assert satisfied
    satisfied, _ = suite_state(suite=id_, task='arkenstone', point='2012')
    assert not satisfied
