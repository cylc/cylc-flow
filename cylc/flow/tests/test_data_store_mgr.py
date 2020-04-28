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

from unittest import main

from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.data_store_mgr import (
    DataStoreMgr, task_mean_elapsed_time, ID_DELIM,
    FAMILY_PROXIES, TASKS, TASK_PROXIES, WORKFLOW
)


class FakeTDef:
    elapsed_times = (0.0, 10.0)


def test_task_mean_elapsed_time():
    tdef = FakeTDef()
    result = task_mean_elapsed_time(tdef)
    assert result == 5.0


class TestDataStoreMgr(CylcWorkflowTestCase):

    suite_name = "five"
    suiterc = """
[meta]
    title = "Inter-cycle dependence + a cold-start task"
[cylc]
    UTC mode = True
[scheduling]
    #runahead limit = 120
    initial cycle point = 20130808T00
    final cycle point = 20130812T00
    [[graph]]
        R1 = "prep => foo"
        PT12H = "foo[-PT12H] => foo => bar"
[visualization]
    initial cycle point = 20130808T00
    final cycle point = 20130808T12
    [[node attributes]]
        foo = "color=red"
        bar = "color=blue"

    """

    def setUp(self) -> None:
        super(TestDataStoreMgr, self).setUp()
        self.data_store_mgr = DataStoreMgr(self.scheduler)
        for name in self.scheduler.config.taskdefs:
            task_proxy = create_task_proxy(
                task_name=name,
                suite_config=self.suite_config,
                is_startup=True
            )
            warnings = self.task_pool.insert_tasks(
                items=[task_proxy.identity],
                stopcp=None,
                check_point=True
            )
            assert 0 == warnings
        self.task_pool.release_runahead_tasks()
        self.data = self.data_store_mgr.data[self.data_store_mgr.workflow_id]

    def test_constructor(self):
        self.assertEqual(
            f'{self.owner}{ID_DELIM}{self.suite_name}',
            self.data_store_mgr.workflow_id
        )
        self.assertFalse(self.data_store_mgr.pool_points)

    def test_generate_definition_elements(self):
        """Test method that generates all definition elements."""
        task_defs = self.scheduler.config.taskdefs.keys()
        self.assertEqual(0, len(self.data[TASKS]))
        self.data_store_mgr.generate_definition_elements()
        self.data_store_mgr.apply_deltas()
        self.assertEqual(len(task_defs), len(self.data[TASKS]))

    def test_generate_graph_elements(self):
        """Test method that generates edge and ghost node elements
        by cycle point."""
        self.data_store_mgr.generate_definition_elements()
        self.data_store_mgr.apply_deltas()
        self.data_store_mgr.pool_points = set(list(self.scheduler.pool.pool))
        tasks_proxies_generated = self.data[TASK_PROXIES]
        self.assertEqual(0, len(tasks_proxies_generated))
        self.data_store_mgr.clear_deltas()
        self.data_store_mgr.generate_graph_elements()
        self.data_store_mgr.apply_deltas()
        self.assertEqual(3, len(tasks_proxies_generated))

    def test_get_data_elements(self):
        """Test method that returns data elements by specified type."""
        flow_msg = self.data_store_mgr.get_data_elements(TASK_PROXIES)
        self.assertEqual(0, len(flow_msg.deltas))
        self.data_store_mgr.initiate_data_model()
        flow_msg = self.data_store_mgr.get_data_elements(TASK_PROXIES)
        self.assertEqual(
            len(flow_msg.deltas),
            len(self.data[TASK_PROXIES]))
        flow_msg = self.data_store_mgr.get_data_elements(WORKFLOW)
        self.assertEqual(
            flow_msg.last_updated, self.data[WORKFLOW].last_updated)
        none_msg = self.data_store_mgr.get_data_elements('fraggle')
        self.assertEqual(0, len(none_msg.ListFields()))

    def test_get_entire_workflow(self):
        """Test method that populates the entire workflow protobuf message."""
        flow_msg = self.data_store_mgr.get_entire_workflow()
        self.assertEqual(0, len(flow_msg.task_proxies))
        self.data_store_mgr.initiate_data_model()
        flow_msg = self.data_store_mgr.get_entire_workflow()
        self.assertEqual(
            len(flow_msg.task_proxies),
            len(self.data[TASK_PROXIES]))

    def test_increment_graph_elements(self):
        """Test method that adds and removes elements by cycle point."""
        self.assertFalse(self.data_store_mgr.pool_points)
        self.assertEqual(0, len(self.data[TASK_PROXIES]))
        self.data_store_mgr.generate_definition_elements()
        self.data_store_mgr.increment_graph_elements()
        self.data_store_mgr.apply_deltas()
        self.assertTrue(self.data_store_mgr.pool_points)
        self.assertEqual(3, len(self.data[TASK_PROXIES]))

    def test_initiate_data_model(self):
        """Test method that generates all data elements in order."""
        self.assertEqual(0, len(self.data[WORKFLOW].task_proxies))
        self.data_store_mgr.initiate_data_model()
        self.assertEqual(3, len(self.data[WORKFLOW].task_proxies))
        self.data_store_mgr.initiate_data_model(reloaded=True)
        self.assertEqual(3, len(self.data[WORKFLOW].task_proxies))

    def test_prune_points(self):
        """Test method that removes data elements by cycle point."""
        self.data_store_mgr.initiate_data_model()
        points = self.data_store_mgr.cycle_states.keys()
        point = next(iter(points))
        self.assertTrue(point in points)
        self.data_store_mgr.clear_deltas()
        self.data_store_mgr.prune_points([point])
        self.data_store_mgr.apply_deltas()
        self.assertTrue(point not in points)

    def test_update_data_structure(self):
        """Test update_data_structure. This method will generate and
        apply deltas/updates given."""
        self.data_store_mgr.initiate_data_model()
        self.assertEqual(0, len(self._collect_states(TASK_PROXIES)))
        update_tasks = self.task_pool.get_all_tasks()
        self.data_store_mgr.update_data_structure(update_tasks)
        self.assertTrue(len(update_tasks) > 0)
        self.assertEqual(
            len(update_tasks), len(self._collect_states(TASK_PROXIES)))

    def test_update_family_proxies(self):
        """Test update_family_proxies. This method will update all
        DataStoreMgr task_proxies of given cycle point strings."""
        self.data_store_mgr.initiate_data_model()
        self.assertEqual(0, len(self._collect_states(FAMILY_PROXIES)))
        update_tasks = self.task_pool.get_all_tasks()
        update_points = set((str(t.point) for t in update_tasks))
        self.data_store_mgr.clear_deltas()
        self.data_store_mgr.update_task_proxies(update_tasks)
        self.data_store_mgr.update_family_proxies(update_points)
        self.data_store_mgr.apply_deltas()
        # Find families in updated cycle points
        point_fams = [
            f.id
            for f in self.data[FAMILY_PROXIES].values()
            if f.cycle_point in update_points]
        self.assertTrue(len(point_fams) > 0)
        self.assertEqual(
            len(point_fams), len(self._collect_states(FAMILY_PROXIES)))

    def test_update_task_proxies(self):
        """Test update_task_proxies. This method will iterate over given
        task instances (TaskProxy), and update any corresponding
        DataStoreMgr task_proxies."""
        self.data_store_mgr.initiate_data_model()
        self.assertEqual(0, len(self._collect_states(TASK_PROXIES)))
        update_tasks = self.task_pool.get_all_tasks()
        self.data_store_mgr.clear_deltas()
        self.data_store_mgr.update_task_proxies(update_tasks)
        self.data_store_mgr.apply_deltas()
        self.assertTrue(len(update_tasks) > 0)
        self.assertEqual(
            len(update_tasks), len(self._collect_states(TASK_PROXIES)))

    def test_update_workflow(self):
        """Test method that updates the dynamic fields of the workflow msg."""
        self.data_store_mgr.generate_definition_elements()
        self.data_store_mgr.apply_deltas()
        old_time = self.data[WORKFLOW].last_updated
        self.data_store_mgr.clear_deltas()
        self.data_store_mgr.update_workflow()
        self.data_store_mgr.apply_deltas()
        new_time = self.data[WORKFLOW].last_updated
        self.assertTrue(new_time > old_time)

    def _collect_states(self, node_type):
        return [
            t.state
            for t in self.data[node_type].values()
            if t.state != ''
        ]


if __name__ == '__main__':
    main()
