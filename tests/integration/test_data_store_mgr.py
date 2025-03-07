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

from logging import INFO
from typing import (
    Iterable,
    List,
    cast,
)

import pytest

from cylc.flow.data_messages_pb2 import (
    PbPrerequisite,
    PbTaskProxy,
)
from cylc.flow.data_store_mgr import (
    EDGES,
    FAMILY_PROXIES,
    JOBS,
    TASK_PROXIES,
    TASKS,
    WORKFLOW,
)
from cylc.flow.id import Tokens
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_outputs import (
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
)
from cylc.flow.wallclock import get_current_time_string


# NOTE: Some of these tests mutate the data store, so running them in
# isolation may see failures when they actually pass if you run the
# whole file


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


def get_pb_prereqs(schd: Scheduler) -> List[PbPrerequisite]:
    """Get all protobuf prerequisites from the data store task proxies."""
    return [
        p
        for t in cast(
            'Iterable[PbTaskProxy]',
            schd.data_store_mgr.updated[TASK_PROXIES].values()
        )
        for p in t.prerequisites
    ]


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
    id_: str = mod_flow(flow_def)
    schd: 'Scheduler' = mod_scheduler(id_)
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
    schd: Scheduler
    schd, data = harness
    assert len(data[WORKFLOW].task_proxies) == 2
    schd.data_store_mgr.initiate_data_model(reloaded=True)
    assert len(data[WORKFLOW].task_proxies) == 2
    # Check n-window preserved on reload:
    schd.data_store_mgr.set_graph_window_extent(2)
    schd.data_store_mgr.update_data_structure()
    assert schd.data_store_mgr.n_edge_distance == 2
    schd.data_store_mgr.initiate_data_model(reloaded=True)
    assert schd.data_store_mgr.n_edge_distance == 2


async def test_delta_task_state(harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = harness
    # follow only needs to happen once .. tests working on the same object?
    w_id = schd.data_store_mgr.workflow_id
    schd.data_store_mgr.data[w_id] = data
    assert TASK_STATUS_FAILED not in set(collect_states(data, TASK_PROXIES))
    for itask in schd.pool.get_tasks():
        itask.state.reset(TASK_STATUS_FAILED)
        schd.data_store_mgr.delta_task_state(itask)
    assert TASK_STATUS_FAILED in set(collect_states(
        schd.data_store_mgr.updated, TASK_PROXIES))

    # put things back the way we found them
    for itask in schd.pool.get_tasks():
        itask.state.reset(TASK_STATUS_WAITING)
        schd.data_store_mgr.delta_task_state(itask)
    await schd.update_data_structure()


async def test_delta_task_held(harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd: Scheduler
    schd, data = harness
    schd.pool.hold_tasks(['*'])
    await schd.update_data_structure()
    assert True in {t.is_held for t in data[TASK_PROXIES].values()}
    for itask in schd.pool.get_tasks():
        itask.state.reset(is_held=False)
        schd.data_store_mgr.delta_task_held(
            itask.tdef.name, itask.point, False
        )
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
    tokens = Tokens(j_id)
    # First update creation
    assert schd.data_store_mgr.updated[JOBS].get('j_id') is None
    schd.data_store_mgr.delta_job_msg(tokens, 'The Atomic Age')
    assert schd.data_store_mgr.updated[JOBS][j_id].messages


def test_delta_job_attr(harness):
    """Test method modifying job fields to job element."""
    schd, data = harness
    schd.data_store_mgr.delta_job_attr(
        Tokens(ext_id(schd)), 'job_runner_name', 'at')
    assert schd.data_store_mgr.updated[JOBS][ext_id(schd)].messages != (
        schd.data_store_mgr.added[JOBS][ext_id(schd)].job_runner_name
    )


def test_delta_job_time(harness):
    """Test method setting job state change time."""
    schd, data = harness
    event_time = get_current_time_string()
    schd.data_store_mgr.delta_job_time(
        Tokens(ext_id(schd)), 'submitted', event_time)
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
    schd.pool.hold_tasks(['*'])
    await schd.update_data_structure()
    assert TASK_STATUS_FAILED not in set(collect_states(data, TASK_PROXIES))
    assert TASK_STATUS_FAILED not in set(collect_states(data, FAMILY_PROXIES))
    assert TASK_STATUS_FAILED not in data[WORKFLOW].state_totals
    assert len({t.is_held for t in data[TASK_PROXIES].values()}) == 2
    for itask in schd.pool.get_tasks():
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
    schd: Scheduler
    schd, data = harness
    schd.pool.set_prereqs_and_outputs(
        schd.pool.get_task_ids(),
        [(TASK_STATUS_SUCCEEDED,)],
        [],
        flow=[]
    )
    assert all(p.satisfied for p in get_pb_prereqs(schd))
    for itask in schd.pool.get_tasks():
        # set prereqs as not-satisfied
        for prereq in itask.state.prerequisites:
            for key in prereq:
                prereq[key] = False
        schd.data_store_mgr.delta_task_prerequisite(itask)
    assert not any(p.satisfied for p in get_pb_prereqs(schd))


async def test_absolute_graph_edges(flow, scheduler, start):
    """It should add absolute graph edges to the store.

    See: https://github.com/cylc/cylc-flow/issues/5845
    """
    runahead_cycles = 1
    id_ = flow({
        'scheduling': {
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'runahead limit': f'P{runahead_cycles}',
            'graph': {
                'R1': 'build',
                'P1': 'build[^] => run',
            },
        },
    })
    schd = scheduler(id_)

    async with start(schd):
        await schd.update_data_structure()

        assert {
            (Tokens(edge.source).relative_id, Tokens(edge.target).relative_id)
            for edge in schd.data_store_mgr.data[schd.id][EDGES].values()
        } == {
            ('1/build', f'{cycle}/run')
            # +1 for Python's range()
            # +2 for Cylc's runahead
            for cycle in range(1, runahead_cycles + 3)
        }


async def test_flow_numbers(flow, scheduler, start):
    """It should update flow numbers when a task is triggered.

    See https://github.com/cylc/cylc-flow/issues/6114
    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'a => b'
            }
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # initialise the data store
        await schd.update_data_structure()

        # the task should exist in the original flow
        ds_task = schd.data_store_mgr.get_data_elements(TASK_PROXIES).added[1]
        assert ds_task.name == 'b'
        assert ds_task.flow_nums == '[1]'

        # force trigger the task in a new flow
        schd.pool.force_trigger_tasks(['1/b'], ['2'])

        # update the data store
        await schd.update_data_structure()

        # the task should now exist in the new flow
        ds_task = schd.data_store_mgr.get_data_elements(TASK_PROXIES).added[1]
        assert ds_task.name == 'b'
        assert ds_task.flow_nums == '[2]'


async def test_delta_task_outputs(one: 'Scheduler', start):
    """Ensure task outputs are inserted into the store.

    Note: Task outputs should *not* be updated incrementally until we have
    a protocol for doing so, see https://github.com/cylc/cylc-flow/pull/6403
    """

    def get_data_outputs():
        """Return satisfied outputs from the *data* store."""
        nonlocal one, itask
        return {
            output.label
            for output in one.data_store_mgr.data[one.id][TASK_PROXIES][
                itask.tokens.id
            ].outputs.values()
            if output.satisfied
        }

    def get_delta_outputs():
        """Return satisfied outputs from the *delta* store.

        Or return None if there's nothing there.
        """
        nonlocal one, itask
        try:
            return {
                output.label
                for output in one.data_store_mgr.updated[TASK_PROXIES][
                    itask.tokens.id
                ].outputs.values()
                if output.satisfied
            }
        except KeyError:
            return None

    def _patch_remove(*args, **kwargs):
        """Prevent the task/workflow from completing."""
        pass

    async with start(one):
        one.pool.remove = _patch_remove

        # create a job submission
        itask = one.pool.get_tasks()[0]
        assert itask
        itask.submit_num += 1
        one.data_store_mgr.insert_job(
            itask.tdef.name, itask.point, itask.state.status, {'submit_num': 1}
        )
        await one.update_data_structure()

        # satisfy the submitted & started outputs
        # (note started implies submitted)
        one.task_events_mgr.process_message(
            itask, 'INFO', TaskEventsManager.EVENT_STARTED
        )

        # the delta should be populated with the newly satisfied outputs
        assert get_data_outputs() == set()
        assert get_delta_outputs() == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
        }

        # the delta should be applied to the store
        await one.update_data_structure()
        assert get_data_outputs() == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
        }
        assert get_delta_outputs() is None

        # satisfy the succeeded output
        one.task_events_mgr.process_message(
            itask, 'INFO', TaskEventsManager.EVENT_SUCCEEDED
        )

        # the delta should be populated with ALL satisfied outputs
        # (not just the newly satisfied output)
        assert get_data_outputs() == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
        }
        assert get_delta_outputs() == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
            TASK_OUTPUT_SUCCEEDED,
        }

        # the delta should be applied to the store
        await one.update_data_structure()
        assert get_data_outputs() == {
            TASK_OUTPUT_SUBMITTED,
            TASK_OUTPUT_STARTED,
            TASK_OUTPUT_SUCCEEDED,
        }
        assert get_delta_outputs() is None


async def test_remove_added_jobs_of_pruned_task(one: Scheduler, start):
    """When a task is pruned, any of its jobs added in the same batch
    must be removed from the batch.

    See https://github.com/cylc/cylc-flow/pull/6656
    """
    async with start(one):
        itask = one.pool.get_tasks()[0]
        itask.state_reset(TASK_STATUS_PREPARING)
        one.task_events_mgr.process_message(itask, INFO, TASK_OUTPUT_SUCCEEDED)
        assert not one.data_store_mgr.data[one.id][JOBS]
        assert len(one.data_store_mgr.added[JOBS]) == 1
        one.data_store_mgr.update_data_structure()
        assert not one.data_store_mgr.data[one.id][JOBS]
        assert not one.data_store_mgr.added[JOBS]
