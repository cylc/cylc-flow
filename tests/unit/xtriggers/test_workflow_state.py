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
import sqlite3
from typing import Any, Callable
from shutil import copytree, rmtree

import pytest

from cylc.flow.dbstatecheck import output_fallback_msg
from cylc.flow.exceptions import WorkflowConfigError, InputError
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.workflow_files import WorkflowFiles
from cylc.flow.xtriggers.workflow_state import (
    _workflow_state_backcompat,
    workflow_state,
    validate,
)
from cylc.flow.xtriggers.suite_state import suite_state


def test_inferred_run(tmp_run_dir: 'Callable', capsys: pytest.CaptureFixture):
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


def test_c7_db_back_compat(tmp_run_dir: 'Callable'):
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
        conn.execute(r"""
            CREATE TABLE task_outputs(
                cycle TEXT, name TEXT, outputs TEXT, PRIMARY KEY(cycle, name)
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
        conn.execute(r"""
            INSERT INTO "task_outputs" VALUES(
                '2012','mithril','{"frodo": "bag end"}'
            );
        """)
        conn.commit()
    finally:
        conn.close()

    # Test workflow_state function
    satisfied, _ = workflow_state(f'{id_}//2012/mithril')
    assert satisfied
    satisfied, _ = workflow_state(f'{id_}//2012/mithril:succeeded')
    assert satisfied
    satisfied, _ = workflow_state(
        f'{id_}//2012/mithril:frodo', is_trigger=True
    )
    assert satisfied
    satisfied, _ = workflow_state(
        f'{id_}//2012/mithril:"bag end"', is_message=True
    )
    assert satisfied

    with pytest.raises(InputError, match='No such task state "pippin"'):
        workflow_state(f'{id_}//2012/mithril:pippin')

    satisfied, _ = workflow_state(id_ + '//2012/arkenstone')
    assert not satisfied

    # Test back-compat (old suite_state function)
    satisfied, _ = suite_state(suite=id_, task='mithril', point='2012')
    assert satisfied
    satisfied, _ = suite_state(
        suite=id_, task='mithril', point='2012', status='succeeded'
    )
    assert satisfied
    satisfied, _ = suite_state(
        suite=id_, task='mithril', point='2012', message='bag end'
    )
    assert satisfied
    satisfied, _ = suite_state(suite=id_, task='arkenstone', point='2012')
    assert not satisfied


def test_c8_db_back_compat(
    tmp_run_dir: 'Callable',
    capsys: pytest.CaptureFixture,
):
    """Test workflow_state xtrigger backwards compatibility with Cylc < 8.3.0
    database."""
    id_ = 'nazgul'
    run_dir: Path = tmp_run_dir(id_)
    db_file = run_dir / 'log' / 'db'
    db_file.parent.mkdir(exist_ok=True)
    # Note: don't use CylcWorkflowDAO here as DB should be frozen
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute(r"""
            CREATE TABLE workflow_params(
                key TEXT, value TEXT, PRIMARY KEY(key)
            );
        """)
        conn.execute(r"""
            CREATE TABLE task_states(
                name TEXT, cycle TEXT, flow_nums TEXT, time_created TEXT,
                time_updated TEXT, submit_num INTEGER, status TEXT,
                flow_wait INTEGER, is_manual_submit INTEGER,
                PRIMARY KEY(name, cycle, flow_nums)
            );
        """)
        conn.execute(r"""
            CREATE TABLE task_outputs(
                cycle TEXT, name TEXT, flow_nums TEXT, outputs TEXT,
                PRIMARY KEY(cycle, name, flow_nums)
            );
        """)
        conn.executemany(
            r'INSERT INTO "workflow_params" VALUES(?,?);',
            [('cylc_version', '8.2.7'),
             ('cycle_point_format', '%Y'),
             ('cycle_point_tz', 'Z')]
        )
        conn.execute(r"""
            INSERT INTO "task_states" VALUES(
                'gimli','2012','[1]','2023-01-30T18:19:15Z',
                '2023-01-30T18:19:15Z',1,'succeeded',0,0
            );
        """)
        conn.execute(r"""
            INSERT INTO "task_outputs" VALUES(
                '2012','gimli','[1]',
                '["submitted", "started", "succeeded", "axe"]'
            );
        """)
        conn.commit()
    finally:
        conn.close()

    gimli = f'{id_}//2012/gimli'

    satisfied, _ = workflow_state(gimli)
    assert satisfied
    satisfied, _ = workflow_state(f'{gimli}:succeeded')
    assert satisfied
    satisfied, _ = workflow_state(f'{gimli}:axe', is_message=True)
    assert satisfied
    _, err = capsys.readouterr()
    assert not err
    # Output label selector falls back to message
    # (won't work if messsage != output label)
    satisfied, _ = workflow_state(f'{gimli}:axe', is_trigger=True)
    assert satisfied
    _, err = capsys.readouterr()
    assert output_fallback_msg in err


def test__workflow_state_backcompat(tmp_run_dir: 'Callable'):
    """Test the _workflow_state_backcompat & suite_state functions on a
    *current* Cylc database."""
    id_ = 'dune'
    run_dir: Path = tmp_run_dir(id_)
    db_file = run_dir / 'log' / 'db'
    db_file.parent.mkdir(exist_ok=True)
    with CylcWorkflowDAO(db_file, create_tables=True) as dao:
        conn = dao.connect()
        conn.executemany(
            r'INSERT INTO "workflow_params" VALUES(?,?);',
            [('cylc_version', '8.3.0'),
             ('cycle_point_format', '%Y'),
             ('cycle_point_tz', 'Z')]
        )
        conn.execute(r"""
            INSERT INTO "task_states" VALUES(
                'arrakis','2012','[1]','2023-01-30T18:19:15Z',
                '2023-01-30T18:19:15Z',1,'succeeded',0,0
            );
        """)
        conn.execute(r"""
            INSERT INTO "task_outputs" VALUES(
                '2012','arrakis','[1]',
                '{"submitted": "submitted", "started": "started", "succeeded": "succeeded", "paul": "lisan al-gaib"}'
            );
        """)
        conn.commit()

    func: Any
    for func in (_workflow_state_backcompat, suite_state):
        satisfied, _ = func(id_, 'arrakis', '2012')
        assert satisfied
        satisfied, _ = func(id_, 'arrakis', '2012', status='succeeded')
        assert satisfied
        # Both output label and message work
        satisfied, _ = func(id_, 'arrakis', '2012', message='paul')
        assert satisfied
        satisfied, _ = func(id_, 'arrakis', '2012', message='lisan al-gaib')
        assert satisfied


def test_validate_ok():
    """Validate returns ok with valid args."""
    validate({
        'workflow_task_id': 'foo//1/bar',
        'is_trigger': False,
        'is_message': False,
        'offset': 'PT1H',
        'flow_num': 44,
    })


@pytest.mark.parametrize(
    'id_', (('foo//1'),)
)
def test_validate_fail_bad_id(id_):
    """Validation failure for bad id"""
    with pytest.raises(WorkflowConfigError, match='Full ID needed'):
        validate({
            'workflow_task_id': id_,
            'offset': 'PT1H',
            'flow_num': 44,
        })


@pytest.mark.parametrize(
    'flow_num', ((4.25260), ('Belguim'))
)
def test_validate_fail_non_int_flow(flow_num):
    """Validate failure for non integer flow numbers."""
    with pytest.raises(WorkflowConfigError, match='must be an integer'):
        validate({
            'workflow_task_id': 'foo//1/bar',
            'offset': 'PT1H',
            'flow_num': flow_num,
        })


def test_validate_polling_config():
    """It should reject invalid or unreliable polling configurations.

    See https://github.com/cylc/cylc-flow/issues/6157
    """
    with pytest.raises(WorkflowConfigError, match='No such task state'):
        validate({
            'workflow_task_id': 'foo//1/bar:elephant',
            'is_trigger': False,
            'is_message': False,
            'flow_num': 44,
        })

    with pytest.raises(WorkflowConfigError, match='Cannot poll for'):
        validate({
            'workflow_task_id': 'foo//1/bar:waiting',
            'is_trigger': False,
            'is_message': False,
            'flow_num': 44,
        })

    with pytest.raises(WorkflowConfigError, match='is not reliable'):
        validate({
            'workflow_task_id': 'foo//1/bar:submitted',
            'is_trigger': False,
            'is_message': False,
            'flow_num': 44,
        })
