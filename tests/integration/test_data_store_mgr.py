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
import pytest

from cylc.flow.data_store_mgr import (
    FAMILY_PROXIES,
    TASKS,
    TASK_PROXIES,
    WORKFLOW
)


@pytest.mark.asyncio
@pytest.fixture(scope='module')
async def harness(mod_flow, mod_scheduler, mod_run, mod_one_conf):
    reg = mod_flow(mod_one_conf)
    schd = mod_scheduler(reg)
    async with mod_run(schd):
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
    assert len(data[TASK_PROXIES]) == 1


def test_initiate_data_model(harness):
    """Test method that generates all data elements in order."""
    schd, data = harness
    assert len(data[WORKFLOW].task_proxies) == 1
    schd.data_store_mgr.initiate_data_model(reloaded=True)
    assert len(data[WORKFLOW].task_proxies) == 1


def test_prune_data_store(harness):
    """Test method that removes data elements by cycle point."""
    schd, data = harness
    for itask in schd.pool.get_all_tasks():
        schd.data_store_mgr.increment_graph_window(
            itask.tdef.name, itask.point, itask.flow_label
        )
    schd.data_store_mgr.apply_deltas()
    schd.data_store_mgr.clear_deltas()
    before_count = len(schd.data_store_mgr.data[
        schd.data_store_mgr.workflow_id][TASK_PROXIES])
    assert before_count > 0
    schd.data_store_mgr.prune_flagged_nodes.update(set(data[TASK_PROXIES]))
    schd.data_store_mgr.prune_data_store()
    schd.data_store_mgr.apply_deltas()
    after_count = len(schd.data_store_mgr.data[
        schd.data_store_mgr.workflow_id][TASK_PROXIES])
    assert after_count < before_count


def test_update_data_structure(harness):
    """Test update_data_structure. This method will generate and
    apply adeltas/updates given."""
    schd, data = harness
    assert len(collect_states(data, TASK_PROXIES)) == 1
    update_tasks = schd.pool.get_all_tasks()
    schd.data_store_mgr.update_data_structure(update_tasks)
    assert len(update_tasks) > 0
    assert len(update_tasks) == len(collect_states(data, TASK_PROXIES))


def test_update_family_proxies(harness):
    """Test update_family_proxies. This method will update all
    DataStoreMgr task_proxies of given cycle point strings."""
    schd, data = harness
    assert len(collect_states(data, FAMILY_PROXIES)) == 1
    update_tasks = schd.pool.get_all_tasks()
    update_points = set((str(t.point) for t in update_tasks))
    schd.data_store_mgr.clear_deltas()
    schd.data_store_mgr.update_task_proxies(update_tasks)
    schd.data_store_mgr.update_family_proxies()
    schd.data_store_mgr.apply_deltas()
    # Find families in updated cycle points
    point_fams = [
        f.id
        for f in data[FAMILY_PROXIES].values()
        if f.cycle_point in update_points
    ]
    assert len(point_fams) > 0
    assert len(point_fams) == len(collect_states(data, FAMILY_PROXIES))


def test_update_task_proxies(harness):
    """Test update_task_proxies. This method will iterate over given
    task instances (TaskProxy), and update any corresponding
    DataStoreMgr task_proxies."""
    schd, data = harness
    assert len(collect_states(data, TASK_PROXIES)) == 1
    update_tasks = schd.pool.get_all_tasks()
    schd.data_store_mgr.clear_deltas()
    schd.data_store_mgr.update_task_proxies(update_tasks)
    schd.data_store_mgr.apply_deltas()
    assert len(update_tasks) > 0
    assert len(update_tasks) == len(collect_states(data, TASK_PROXIES))


@pytest.mark.skip('TODO: fix this test')
def test_update_workflow(harness):
    """Test method that updates the dynamic fields of the workflow msg."""
    schd, data = harness
    schd.data_store_mgr.apply_deltas()
    old_time = data[WORKFLOW].last_updated
    schd.data_store_mgr.clear_deltas()
    schd.data_store_mgr.update_workflow()
    schd.data_store_mgr.apply_deltas()
    new_time = data[WORKFLOW].last_updated
    assert new_time > old_time
