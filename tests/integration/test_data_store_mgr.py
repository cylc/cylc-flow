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

import logging
from logging import INFO
from typing import (
    Iterable,
    List,
    cast,
)
from unittest.mock import Mock

import pytest

from cylc.flow import LOG
from cylc.flow.commands import (
    force_trigger_tasks,
    run_cmd,
)
from cylc.flow.data_messages_pb2 import (
    PbJob,
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
from cylc.flow.id import (
    TaskTokens,
    Tokens,
)
from cylc.flow.network.log_stream_handler import ProtobufStreamHandler
from cylc.flow.scheduler import Scheduler
from cylc.flow.task_events_mgr import TaskEventsManager
from cylc.flow.task_outputs import (
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
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


def get_pb_prereqs(schd: 'Scheduler') -> 'List[PbPrerequisite]':
    """Get all protobuf prerequisites from the data store task proxies."""
    return [
        p
        for t in cast(
            'Iterable[PbTaskProxy]',
            schd.data_store_mgr.updated[TASK_PROXIES].values()
        )
        for p in t.prerequisites
    ]


def get_pb_job(schd: Scheduler, itask: TaskProxy) -> PbJob:
    """Get the protobuf job for a given task from the data store."""
    return schd.data_store_mgr.data[schd.id][JOBS][itask.job_tokens.id]


@pytest.fixture(scope='module')
async def mod_harness(mod_flow, mod_scheduler, mod_start):
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


@pytest.fixture(scope='module')
async def edgeharness(mod_flow, mod_scheduler, mod_start):
    """Graph with > n in window edge at n=1."""
    flow_def = {
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': """
                    b1 & b2 => c1 & c2
                    c1 => c2
                """
            }
        }
    }
    id_: str = mod_flow(flow_def)
    schd: 'Scheduler' = mod_scheduler(id_)
    async with mod_start(schd):
        await schd.update_data_structure()
        data = schd.data_store_mgr.data[schd.data_store_mgr.workflow_id]
        yield schd, data


@pytest.fixture(scope='module')
async def xharness(mod_flow, mod_scheduler, mod_start):
    """Like harness, but add xtriggers."""
    flow_def = {
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'xtriggers': {
                'x': 'xrandom(0)',
                'x2': 'xrandom(0)',
                'y': 'xrandom(0, _=1)'
            },
            'graph': {
                'R1': """
                    @x => foo
                    @x2 => foo
                    @y => foo
                    @x => bar
                """
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


def test_generate_definition_elements(mod_harness):
    """Test method that generates all definition elements."""
    schd, data = mod_harness
    task_defs = schd.config.taskdefs.keys()
    assert len(data[TASKS]) == len(task_defs)
    assert len(data[TASK_PROXIES]) == len(task_defs)


def test_generate_graph_elements(mod_harness):
    schd, data = mod_harness
    task_defs = schd.config.taskdefs.keys()
    assert len(data[TASK_PROXIES]) == len(task_defs)


def test_get_data_elements(mod_harness):
    schd, data = mod_harness
    flow_msg = schd.data_store_mgr.get_data_elements(TASK_PROXIES)
    assert len(flow_msg.added) == len(data[TASK_PROXIES])

    flow_msg = schd.data_store_mgr.get_data_elements(WORKFLOW)
    assert flow_msg.added.last_updated == data[WORKFLOW].last_updated

    none_msg = schd.data_store_mgr.get_data_elements('fraggle')
    assert len(none_msg.ListFields()) == 0


def test_get_entire_workflow(mod_harness):
    """Test method that populates the entire workflow protobuf message."""
    schd, data = mod_harness
    flow_msg = schd.data_store_mgr.get_entire_workflow()
    assert len(flow_msg.task_proxies) == len(data[TASK_PROXIES])


def test_increment_graph_window(mod_harness):
    """Test method that adds and removes elements window boundary."""
    schd, data = mod_harness
    assert schd.data_store_mgr.prune_trigger_nodes
    assert len(data[TASK_PROXIES]) == 2


def test_in_window_extra_edges(edgeharness):
    """Test edges beyond walk but within window are generated."""
    schd, data = edgeharness
    w_id = schd.data_store_mgr.workflow_id
    assert f'{w_id}//$edge|1/c1|1/c2' in data[EDGES]


def test_initiate_data_model(mod_harness):
    """Test method that generates all data elements in order."""
    schd: Scheduler
    schd, data = mod_harness
    assert len(data[WORKFLOW].task_proxies) == 2
    schd.data_store_mgr.initiate_data_model(reloaded=True)
    assert len(data[WORKFLOW].task_proxies) == 2
    # Check n-window preserved on reload:
    schd.data_store_mgr.set_graph_window_extent(2)
    schd.data_store_mgr.update_data_structure()
    assert schd.data_store_mgr.n_edge_distance == 2
    schd.data_store_mgr.initiate_data_model(reloaded=True)
    assert schd.data_store_mgr.n_edge_distance == 2


async def test_delta_task_state(mod_harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = mod_harness
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


async def test_delta_task_held(mod_harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd: Scheduler
    schd, data = mod_harness
    schd.pool.hold_tasks({TaskTokens('*', 'root')})
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
    schd.pool.release_held_tasks({TaskTokens('*', 'root')})
    await schd.update_data_structure()


def test_insert_job(mod_harness):
    """Test method that adds a new job to the store."""
    schd: Scheduler
    schd, data = mod_harness
    assert len(schd.data_store_mgr.added[JOBS]) == 0
    itask = schd.pool.get_tasks()[0]
    schd.data_store_mgr.insert_job(itask, 'submitted', job_config(schd))
    assert len(schd.data_store_mgr.added[JOBS]) == 1
    assert ext_id(schd) in schd.data_store_mgr.added[JOBS]


def test_insert_db_job(mod_harness, job_db_row):
    """Test method that adds a new job from the db to the store."""
    schd: Scheduler
    schd, data = mod_harness
    assert len(schd.data_store_mgr.added[JOBS]) == 1
    schd.data_store_mgr.insert_db_job(0, job_db_row)
    assert len(schd.data_store_mgr.added[JOBS]) == 2
    assert ext_id(schd) in schd.data_store_mgr.added[JOBS]


def test_delta_job_msg(mod_harness):
    """Test method adding messages to job element."""
    schd: Scheduler
    schd, data = mod_harness
    j_id = ext_id(schd)
    tokens = Tokens(j_id)
    # First update creation
    assert schd.data_store_mgr.updated[JOBS].get('j_id') is None
    schd.data_store_mgr.delta_job_msg(tokens, 'The Atomic Age')
    assert schd.data_store_mgr.updated[JOBS][j_id].messages


def test_delta_job_attr(mod_harness):
    """Test method modifying job fields to job element."""
    schd: Scheduler
    schd, data = mod_harness
    schd.data_store_mgr.delta_job_attr(
        Mock(job_tokens=Tokens(ext_id(schd))), 'job_runner_name', 'at'
    )
    assert schd.data_store_mgr.updated[JOBS][ext_id(schd)].messages != (
        schd.data_store_mgr.added[JOBS][ext_id(schd)].job_runner_name
    )


def test_delta_job_time(mod_harness):
    """Test method setting job state change time."""
    schd: Scheduler
    schd, data = mod_harness
    event_time = get_current_time_string()
    schd.data_store_mgr.delta_job_time(
        Mock(job_tokens=Tokens(ext_id(schd))), 'submitted', event_time
    )
    job_updated = schd.data_store_mgr.updated[JOBS][ext_id(schd)]
    with pytest.raises(ValueError):
        job_updated.HasField('jumped_time')
    assert job_updated.submitted_time != (
        schd.data_store_mgr.added[JOBS][ext_id(schd)].submitted_time
    )


async def test_update_data_structure(mod_harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = mod_harness
    w_id = schd.data_store_mgr.workflow_id
    schd.data_store_mgr.data[w_id] = data
    schd.pool.hold_tasks({TaskTokens('*', 'root')})
    await schd.update_data_structure()
    assert TASK_STATUS_FAILED not in set(collect_states(data, TASK_PROXIES))
    assert TASK_STATUS_FAILED not in set(collect_states(data, FAMILY_PROXIES))
    assert TASK_STATUS_FAILED not in data[WORKFLOW].state_totals
    assert len({t.id for t in data[TASK_PROXIES].values() if t.is_held}) == 2
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


async def test_prune_data_store(flow, scheduler, start):
    """Test prune_data_store. This method will expand and reduce the data-store
    to invoke pruning.

    Also test rapid addition and removal of families (as happens with suicide
    triggers):
    https://github.com/cylc/cylc-ui/issues/1999

    """
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo => bar'
            }
        },
        'runtime': {
            'FOOBAR': {},
            'FOO': {
                'inherit': 'FOOBAR'
            },
            'foo': {
                'inherit': 'FOO'
            },
            'BAR': {
                'inherit': 'FOOBAR'
            },
            'bar': {
                'inherit': 'BAR'
            }
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # initialise the data store
        await schd.update_data_structure()
        w_id = schd.data_store_mgr.workflow_id
        data = schd.data_store_mgr.data[w_id]
        schd.pool.hold_tasks({TaskTokens('*', 'root')})
        await schd.update_data_structure()
        assert (
            len({t.id for t in data[TASK_PROXIES].values() if t.is_held}) == 2
        )

        # Window size reduction to invoke pruning
        schd.data_store_mgr.set_graph_window_extent(0)
        schd.data_store_mgr.update_data_structure()
        assert (
            len({t.id for t in data[TASK_PROXIES].values() if t.is_held}) == 1
        )

        # Test rapid addition and removal
        # bar/BAR task/family proxies not in .added
        assert len({
            t.name
            for t in schd.data_store_mgr.added[TASK_PROXIES].values()
            if t.name == 'bar'
        }) == 0
        assert len({
            f.name
            for f in schd.data_store_mgr.added[FAMILY_PROXIES].values()
            if f.name == 'BAR'
        }) == 0
        # Add bar/BAR on set output of foo
        for itask in schd.pool.get_tasks():
            schd.pool.spawn_on_output(itask, TASK_OUTPUT_SUCCEEDED)
        # bar/BAR now found.
        assert len({
            t.name
            for t in schd.data_store_mgr.added[TASK_PROXIES].values()
            if t.name == 'bar'
        }) == 1
        assert len({
            f.name
            for f in schd.data_store_mgr.added[FAMILY_PROXIES].values()
            if f.name == 'BAR'
        }) == 1
        # Before updating the data-store, remove bar/BAR.
        schd.pool.remove(schd.pool._get_task_by_id('1/bar'), 'Test removal')
        schd.data_store_mgr.update_data_structure()
        # bar/BAR not found in data or added stores.
        assert len({
            t.name
            for t in data[TASK_PROXIES].values()
            if t.name == 'bar'
        }) == 0
        assert len({
            t.name
            for t in schd.data_store_mgr.added[TASK_PROXIES].values()
            if t.name == 'bar'
        }) == 0
        assert len({
            f.name
            for f in data[FAMILY_PROXIES].values()
            if f.name == 'BAR'
        }) == 0
        assert len({
            f.name
            for f in schd.data_store_mgr.added[FAMILY_PROXIES].values()
            if f.name == 'BAR'
        }) == 0


async def test_family_ascent_point_prune(mod_harness):
    """Test _family_ascent_point_prune. This method tries to remove
    non-existent family."""
    schd, data = mod_harness
    fp_id = 'NotAFamilyProxy'
    parent_ids = {fp_id}
    checked_ids = set()
    node_ids = set()
    schd.data_store_mgr._family_ascent_point_prune(
        next(iter(parent_ids)),
        node_ids,
        parent_ids,
        checked_ids,
        schd.data_store_mgr.family_pruned_ids
    )
    assert len(checked_ids) == 1
    assert len(parent_ids) == 0


def test_delta_task_prerequisite(mod_harness):
    """Test delta_task_prerequisites."""
    schd: Scheduler
    schd, data = mod_harness
    schd.pool.set_prereqs_and_outputs(
        {itask.tokens for itask in schd.pool.get_tasks()},
        [TASK_STATUS_SUCCEEDED],
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


def test_delta_task_xtrigger(xharness):
    """Test delta_task_xtrigger."""
    schd: Scheduler
    schd, _ = xharness
    foo = schd.pool._get_task_by_id('1/foo')
    bar = schd.pool._get_task_by_id('1/bar')

    assert not foo.state.xtriggers['x']   # not satisfied
    assert not foo.state.xtriggers['x2']  # not satisfied
    assert not foo.state.xtriggers['y']   # not satisfied
    assert not bar.state.xtriggers['x']   # not satisfied

    # satisfy foo's dependence on x
    schd.pool.set_prereqs_and_outputs(
        {TaskTokens('1', 'foo')},
        [],
        ['xtrigger/x:succeeded'],
        flow=[]
    )

    # check the task pool
    assert foo.state.xtriggers['x']  # satisfied
    assert not foo.state.xtriggers['y']  # satisfied
    assert not bar.state.xtriggers['x']  # not satisfied

    # data store should have one updated task proxy with satisfied xtrigger x
    [pbfoo] = schd.data_store_mgr.updated[TASK_PROXIES].values()
    assert pbfoo.id.endswith('foo')
    xtrig = pbfoo.xtriggers['x=xrandom(0)']
    assert xtrig.label == 'x'
    assert xtrig.satisfied

    # unsatisfy it again
    schd.pool.set_prereqs_and_outputs(
        {TaskTokens('1', 'foo')},
        [],
        ['xtrigger/x:unsatisfied'],
        flow=[]
    )

    # check the task pool
    assert not foo.state.xtriggers['x']  # not satisfied

    # data store should have one updated task proxy with unsatisfied xtrigger x
    [pbfoo] = schd.data_store_mgr.updated[TASK_PROXIES].values()
    assert pbfoo.id.endswith('foo')
    xtrig = pbfoo.xtriggers['x=xrandom(0)']
    assert xtrig.label == 'x'
    assert not xtrig.satisfied

    # satisfy both of foo's xtriggers at once
    schd.pool.set_prereqs_and_outputs(
        {TaskTokens('1', 'foo')},
        [],
        ['xtrigger/all:succeeded'],
        flow=[]
    )

    # check the task pool
    assert foo.state.xtriggers['x']  # satisfied
    assert foo.state.xtriggers['y']  # satisfied

    # data store should have one updated task proxy with satisfied xtrigger x
    [pbfoo] = schd.data_store_mgr.updated[TASK_PROXIES].values()
    assert pbfoo.id.endswith('foo')

    xtrig_x = pbfoo.xtriggers['x=xrandom(0)']
    assert xtrig_x.label == 'x'
    assert xtrig_x.satisfied

    # updated task proxy should also contain duplicate xtrigger labels
    xtrig_x2 = pbfoo.xtriggers['x2=xrandom(0)']
    assert xtrig_x2.label == 'x2'
    assert xtrig_x2.satisfied

    xtrig_y = pbfoo.xtriggers['y=xrandom(0, _=1)']
    assert xtrig_y.label == 'y'
    assert xtrig_y.satisfied


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

        # the task should not have a flow number as it is n>0
        ds_task = schd.data_store_mgr.get_data_elements(TASK_PROXIES).added[1]
        assert ds_task.name == 'b'
        assert ds_task.flow_nums == '[]'

        # force trigger the task in a new flow
        await run_cmd(force_trigger_tasks(schd, ['1/b'], ['2']))

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
            itask, itask.state.status, {'submit_num': 1}
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


async def test_log_events(one: Scheduler, start):
    """It should record log events and strip and ANSI formatting."""
    async with start(one):
        handler = ProtobufStreamHandler(
            one,
            level=logging.INFO,
        )
        LOG.addHandler(handler)

        try:
            # log a message with some ANSIMARKUP formatting
            LOG.warning(
                '<bold>here</bold> <red>hare</red> <yellow>here</yellow>'
            )

            await one.update_data_structure()
            log_records = one.data_store_mgr.data[one.id][WORKFLOW].log_records

            assert len(log_records) == 1
            log_record = log_records[0]

            # the message should be in the store, the ANSI formatting should be
            # stripped
            assert log_record.level == 'WARNING'
            assert log_record.message == 'here hare here'
        finally:
            LOG.removeHandler(handler)


async def test_no_backwards_job_state_change(one: Scheduler, start):
    """It should not allow backwards job state changes."""
    async with start(one):
        itask = one.pool.get_tasks()[0]
        itask.state_reset(TASK_STATUS_PREPARING)
        itask.submit_num += 1
        await one.update_data_structure()

        one.task_events_mgr.process_message(itask, INFO, TASK_OUTPUT_STARTED)
        await one.update_data_structure()
        assert get_pb_job(one, itask).state == TASK_STATUS_RUNNING

        # Simulate late arrival of "submitted" message
        one.task_events_mgr.process_message(itask, INFO, TASK_OUTPUT_SUBMITTED)
        await one.update_data_structure()
        assert get_pb_job(one, itask).state == TASK_STATUS_RUNNING


async def test_job_estimated_finish_time(one_conf, flow, scheduler, start):
    """It should set estimated_finish_time on job elements along with
    started_time."""
    wid = flow({
        **one_conf,
        'scheduler': {'UTC mode': True},
        'runtime': {
            'one': {'execution time limit': 'PT2M'},
        },
    })
    schd: Scheduler = scheduler(wid)
    date = '2081-07-02T'

    async def start_job(itask: TaskProxy, start_time: str):
        if not schd.pool.get_task(itask.point, itask.tdef.name):
            schd.pool.add_to_pool(itask)
            await schd.update_data_structure()
        itask.state_reset(TASK_STATUS_PREPARING)
        itask.submit_num += 1
        itask.jobs = []
        schd.task_events_mgr.process_message(
            itask, INFO, TASK_OUTPUT_SUBMITTED  # submit time irrelevant
        )
        await schd.update_data_structure()
        schd.task_events_mgr.process_message(
            itask, INFO, TASK_OUTPUT_STARTED, f'{date}{start_time}'
        )
        await schd.update_data_structure()

    async with start(schd):
        itask = schd.pool.get_tasks()[0]
        await start_job(itask, '06:00:00Z')
        # 1st job: estimate based on execution time limit:
        assert (
            get_pb_job(schd, itask).estimated_finish_time
            == f'{date}06:02:00Z'
        )

        # Finish this job and start a new one:
        schd.task_events_mgr.process_message(
            itask, INFO, TASK_OUTPUT_SUCCEEDED, f'{date}06:00:40Z'
        )
        await start_job(itask, '06:01:00Z')
        # >=2nd job: estimate based on mean of previous jobs:
        assert (
            get_pb_job(schd, itask).estimated_finish_time
            == f'{date}06:01:40Z'
        )
