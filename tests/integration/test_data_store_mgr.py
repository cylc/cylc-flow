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

import asyncio
from pathlib import Path
import sqlite3
import pytest
from typing import TYPE_CHECKING

from cylc.flow.data_store_mgr import (
    FAMILY_PROXIES,
    JOBS,
    TASKS,
    TASK_PROXIES,
    WORKFLOW
)
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.rundb import CylcWorkflowDAO as DAO
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.workflow_files import WorkflowFiles, get_workflow_srv_dir

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


# NOTE: These tests mutate the data store, so running them in isolation may
# see failures when they actually pass if you run the whole file


def job_config(schd):
    return {
        'owner': schd.owner,
        'submit_num': 3,
        'task_id': '1/foo',
        'job_runner_name': 'background',
        'env-script': None,
        'err-script': None,
        'exit-script': None,
        'execution_time_limit': None,
        'init-script': None,
        'post-script': None,
        'pre-script': None,
        'script': 'sleep 5; echo "I come in peace"',
        'work_d': None,
        'directives': {},
        'environment': {},
        'param_var': {},
        'logfiles': [],
        'platform': {'name': 'platform'},
    }


@pytest.fixture
def job_db_row():
    return [
        '1',
        'foo',
        4,
        '2020-04-03T13:40:18+13:00',
        0,
        '2020-04-03T13:40:20+13:00',
        None,
        None,
        'background',
        '20542',
        'localhost',
    ]


def int_id(_):
    return '1/foo/03'


def ext_id(schd):
    return f'~{schd.owner}/{schd.workflow}//{int_id(None)}'


@pytest.fixture(scope='module')
async def harness(mod_flow, mod_scheduler, mod_start):
    flow_def = {
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': 'foo => bar'
            }
        }
    }
    reg: str = mod_flow(flow_def)
    schd: 'Scheduler' = mod_scheduler(reg)
    async with mod_start(schd):
        await schd.update_data_structure()
        data = schd.data_store_mgr.data[schd.data_store_mgr.workflow_id]
        yield schd, data


def collect_states(data, node_type):
    return [
        t.state
        for t in data[node_type].values()
        if t.state != ''
    ]


def test_generate_definition_elements(harness):
    """Test method that generates all definition elements."""
    schd, data = harness
    task_defs = schd.config.taskdefs.keys()
    assert len(data[TASKS]) == len(task_defs)
    assert len(data[TASK_PROXIES]) == len(task_defs)


def test_generate_graph_elements(harness):
    schd, data = harness
    task_defs = schd.config.taskdefs.keys()
    assert len(data[TASK_PROXIES]) == len(task_defs)


def test_get_data_elements(harness):
    schd, data = harness
    flow_msg = schd.data_store_mgr.get_data_elements(TASK_PROXIES)
    assert len(flow_msg.added) == len(data[TASK_PROXIES])

    flow_msg = schd.data_store_mgr.get_data_elements(WORKFLOW)
    assert flow_msg.added.last_updated == data[WORKFLOW].last_updated

    none_msg = schd.data_store_mgr.get_data_elements('fraggle')
    assert len(none_msg.ListFields()) == 0


def test_get_entire_workflow(harness):
    """Test method that populates the entire workflow protobuf message."""
    schd, data = harness
    flow_msg = schd.data_store_mgr.get_entire_workflow()
    assert len(flow_msg.task_proxies) == len(data[TASK_PROXIES])


def test_increment_graph_window(harness):
    """Test method that adds and removes elements window boundary."""
    schd, data = harness
    assert schd.data_store_mgr.prune_trigger_nodes
    assert len(data[TASK_PROXIES]) == 2


def test_initiate_data_model(harness):
    """Test method that generates all data elements in order."""
    schd, data = harness
    assert len(data[WORKFLOW].task_proxies) == 2
    schd.data_store_mgr.initiate_data_model(reloaded=True)
    assert len(data[WORKFLOW].task_proxies) == 2


async def test_delta_task_state(harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = harness
    # follow only needs to happen once .. tests working on the same object?
    w_id = schd.data_store_mgr.workflow_id
    schd.data_store_mgr.data[w_id] = data
    assert TASK_STATUS_FAILED not in set(collect_states(data, TASK_PROXIES))
    for itask in schd.pool.get_all_tasks():
        itask.state.reset(TASK_STATUS_FAILED)
        schd.data_store_mgr.delta_task_state(itask)
    assert TASK_STATUS_FAILED in set(collect_states(
        schd.data_store_mgr.updated, TASK_PROXIES))

    # put things back the way we found them
    for itask in schd.pool.get_all_tasks():
        itask.state.reset(TASK_STATUS_WAITING)
        schd.data_store_mgr.delta_task_state(itask)
    await schd.update_data_structure()


async def test_delta_task_held(harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = harness
    schd.pool.hold_tasks('*')
    await schd.update_data_structure()
    assert True in {t.is_held for t in data[TASK_PROXIES].values()}
    for itask in schd.pool.get_all_tasks():
        itask.state.reset(is_held=False)
        schd.data_store_mgr.delta_task_held(itask)
    assert True not in {
        t.is_held
        for t in schd.data_store_mgr.updated[TASK_PROXIES].values()
    }

    # put things back the way we found them
    schd.pool.release_held_tasks('*')
    await schd.update_data_structure()


def test_insert_job(harness):
    """Test method that adds a new job to the store."""
    schd, data = harness
    assert len(schd.data_store_mgr.added[JOBS]) == 0
    schd.data_store_mgr.insert_job('foo', '1', 'submitted', job_config(schd))
    assert len(schd.data_store_mgr.added[JOBS]) == 1
    assert ext_id(schd) in schd.data_store_mgr.added[JOBS]


def test_insert_db_job(harness, job_db_row):
    """Test method that adds a new job from the db to the store."""
    schd, data = harness
    assert len(schd.data_store_mgr.added[JOBS]) == 1
    schd.data_store_mgr.insert_db_job(0, job_db_row)
    assert len(schd.data_store_mgr.added[JOBS]) == 2
    assert ext_id(schd) in schd.data_store_mgr.added[JOBS]


def test_delta_job_msg(harness):
    """Test method adding messages to job element."""
    schd, data = harness
    j_id = ext_id(schd)
    job_d = int_id(schd)
    # First update creation
    assert schd.data_store_mgr.updated[JOBS].get('j_id') is None
    schd.data_store_mgr.delta_job_msg(job_d, 'The Atomic Age')
    assert schd.data_store_mgr.updated[JOBS][j_id].messages


def test_delta_job_attr(harness):
    """Test method modifying job fields to job element."""
    schd, data = harness
    schd.data_store_mgr.delta_job_attr(
        int_id(schd), 'exit_script', 'rm -v *')
    assert schd.data_store_mgr.updated[JOBS][ext_id(schd)].messages != (
        schd.data_store_mgr.added[JOBS][ext_id(schd)].exit_script
    )


def test_delta_job_time(harness):
    """Test method setting job state change time."""
    schd, data = harness
    event_time = get_current_time_string()
    schd.data_store_mgr.delta_job_time(
        int_id(schd), 'submitted', event_time)
    job_updated = schd.data_store_mgr.updated[JOBS][ext_id(schd)]
    with pytest.raises(ValueError):
        job_updated.HasField('jumped_time')
    assert job_updated.submitted_time != (
        schd.data_store_mgr.added[JOBS][ext_id(schd)].submitted_time
    )


async def test_update_data_structure(harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = harness
    w_id = schd.data_store_mgr.workflow_id
    schd.data_store_mgr.data[w_id] = data
    schd.pool.hold_tasks('*')
    await schd.update_data_structure()
    assert TASK_STATUS_FAILED not in set(collect_states(data, TASK_PROXIES))
    assert TASK_STATUS_FAILED not in set(collect_states(data, FAMILY_PROXIES))
    assert TASK_STATUS_FAILED not in data[WORKFLOW].state_totals
    assert len({t.is_held for t in data[TASK_PROXIES].values()}) == 2
    for itask in schd.pool.get_all_tasks():
        itask.state.reset(TASK_STATUS_FAILED)
        schd.data_store_mgr.delta_task_state(itask)
    schd.data_store_mgr.update_data_structure()
    # State change applied
    assert TASK_STATUS_FAILED in set(collect_states(data, TASK_PROXIES))
    # family state changed and applied
    assert TASK_STATUS_FAILED in set(collect_states(data, FAMILY_PROXIES))
    # state totals changed
    assert TASK_STATUS_FAILED in data[WORKFLOW].state_totals
    # Shows pruning worked
    # TODO: fixme
    # https://github.com/cylc/cylc-flow/issues/4175#issuecomment-1025666413
    # assert len({t.is_held for t in data[TASK_PROXIES].values()}) == 1


def test_delta_task_prerequisite(harness):
    """Test delta_task_prerequisites."""
    schd, data = harness
    schd.pool.force_spawn_children([
        t.identity
        for t in schd.pool.get_all_tasks()
    ], (TASK_STATUS_SUCCEEDED,), "flow1")
    assert all({
        p.satisfied
        for t in schd.data_store_mgr.updated[TASK_PROXIES].values()
        for p in t.prerequisites})
    for itask in schd.pool.get_all_tasks():
        itask.state.set_prerequisites_not_satisfied()
        schd.data_store_mgr.delta_task_prerequisite(itask)
    assert not any({
        p.satisfied
        for t in schd.data_store_mgr.updated[TASK_PROXIES].values()
        for p in t.prerequisites})


@pytest.fixture
def ghost_job_db(request: pytest.FixtureRequest):
    """Provide workflow DB for "ghost job" test."""
    db_dump = (
        request.path.parent / 'fixture-data' / 'ghost-job.sqlite3'
    ).read_text()

    def _ghost_job_db(srv_dir_path):
        srv_dir_path = Path(srv_dir_path)
        srv_dir_path.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(srv_dir_path / WorkflowFiles.Service.DB)
        cur = con.cursor()
        cur.executescript(db_dump)
        con.close()

    return _ghost_job_db


async def test_ghost_job(
    flow, one_conf, scheduler, run, ghost_job_db, db_select, gql_query
):
    """Test restarting when there is a "ghost job" in the DB
    (has a submit_time in task_jobs table but no submit_exit_time or run_time)
    """
    reg = flow(one_conf)
    ghost_job_db(get_workflow_srv_dir(reg))
    schd: Scheduler = scheduler(reg, paused_start=True)

    db_columns = ('cycle', 'name', 'submit_num')

    async with run(schd):
        client = WorkflowRuntimeClient(reg)
        await asyncio.sleep(1)  # yields control to main loop

        # There will be 1 ghost job in DB:
        assert db_select(
            schd, False, DAO.TABLE_TASK_JOBS, *db_columns
        ) == [
            ('1', 'one', 1)
        ]
        # Get submit timestamp for that job:
        orig_submit_time = db_select(
            schd, False, DAO.TABLE_TASK_JOBS, 'time_submit'
        )[0][0]
        # Ghost job should not be in data store:
        assert await gql_query(client, '''
            jobs {
                cyclePoint, name, submitNum
            }
        ''') == {'jobs': []}

        schd.resume_workflow()
        await asyncio.sleep(1)  # yields control to main loop

        # Job should now be in data store:
        # assert await gql_query(client, '''
        #     jobs {
        #         cyclePoint, name, submitNum
        #     }
        # ''') == {
        #     'jobs': [{
        #         'cyclePoint': '1',
        #         'name': 'one',
        #         'submitNum': 1
        #     }]
        # }
        # Job should have same submit number in DB:
        assert db_select(
            schd, False, DAO.TABLE_TASK_JOBS, *db_columns
        ) == [
            ('1', 'one', 1)
        ]
        # Job should have new submit timestamp:
        assert db_select(
            schd, False, DAO.TABLE_TASK_JOBS, 'time_submit'
        )[0][0] != orig_submit_time
