#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
from cylc.flow.ws_data_mgr import (
    WsDataMgr, task_mean_elapsed_time, ID_DELIM,
    EDGES, FAMILY_PROXIES, TASKS, TASK_PROXIES, WORKFLOW
)


class FakeTDef:
    elapsed_times = (0.0, 10.0)


def test_task_mean_elapsed_time():
    tdef = FakeTDef()
    result = task_mean_elapsed_time(tdef)
    assert result == 5.0


class TestWsDataMgr(CylcWorkflowTestCase):

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
        super(TestWsDataMgr, self).setUp()
        self.ws_data_mgr = WsDataMgr(self.scheduler)
        for name in self.scheduler.config.taskdefs:
            task_proxy = create_task_proxy(
                task_name=name,
                suite_config=self.suite_config,
                is_startup=True
            )
            warnings = self.task_pool.insert_tasks(
                items=[task_proxy.identity],
                stopcp=None,
                no_check=False
            )
            assert 0 == warnings
        self.task_pool.release_runahead_tasks()
        self.data = self.ws_data_mgr.data[self.ws_data_mgr.workflow_id]

    def test_constructor(self):
        self.assertEqual(
            f'{self.owner}{ID_DELIM}{self.suite_name}',
            self.ws_data_mgr.workflow_id
        )
        self.assertFalse(self.ws_data_mgr.pool_points)

    def test_generate_definition_elements(self):
        """Test method that generates all definition elements."""
        task_defs = self.scheduler.config.taskdefs.keys()
        self.assertEqual(0, len(self.data[TASKS]))
        self.ws_data_mgr.generate_definition_elements()
        self.assertEqual(len(task_defs), len(self.data[TASKS]))

    def test_generate_graph_elements(self):
        """Test method that generates edge and ghost node elements
        by cycle point."""
        self.ws_data_mgr.generate_definition_elements()
        self.ws_data_mgr.pool_points = set(list(self.scheduler.pool.pool))
        tasks_proxies_generated = self.data[TASK_PROXIES]
        self.assertEqual(0, len(tasks_proxies_generated))
        self.ws_data_mgr.generate_graph_elements(
            self.data[EDGES],
            self.data[TASK_PROXIES],
            self.data[FAMILY_PROXIES]
        )
        self.assertEqual(3, len(tasks_proxies_generated))

    def test_get_entire_workflow(self):
        """Test method that populates the entire workflow protobuf message."""
        flow_msg = self.ws_data_mgr.get_entire_workflow()
        self.assertEqual(0, len(flow_msg.task_proxies))
        self.ws_data_mgr.initiate_data_model()
        flow_msg = self.ws_data_mgr.get_entire_workflow()
        self.assertEqual(
            len(flow_msg.task_proxies),
            len(self.data[TASK_PROXIES]))

    def test_increment_graph_elements(self):
        """Test method that adds and removes elements by cycle point."""
        self.assertFalse(self.ws_data_mgr.pool_points)
        self.assertEqual(0, len(self.data[TASK_PROXIES]))
        self.ws_data_mgr.generate_definition_elements()
        self.ws_data_mgr.increment_graph_elements()
        self.assertTrue(self.ws_data_mgr.pool_points)
        self.assertEqual(3, len(self.data[TASK_PROXIES]))

    def test_initiate_data_model(self):
        """Test method that generates all data elements in order."""
        self.assertEqual(0, len(self.data[WORKFLOW].task_proxies))
        self.ws_data_mgr.initiate_data_model()
        self.assertEqual(3, len(self.data[WORKFLOW].task_proxies))

    def test_prune_points(self):
        """Test method that removes data elements by cycle point."""
        self.ws_data_mgr.generate_definition_elements()
        self.ws_data_mgr.increment_graph_elements()
        points = self.ws_data_mgr.cycle_states.keys()
        point = next(iter(points))
        self.assertTrue(point in points)
        self.ws_data_mgr.prune_points([point])
        self.assertTrue(point not in points)

    def test_update_family_proxies(self):
        """Test update_family_proxies. This method will update all
        WsDataMgr task_proxies of given cycle point strings."""
        self.ws_data_mgr.generate_definition_elements()
        self.ws_data_mgr.increment_graph_elements()
        self.assertEqual(0, len(self._collect_states(FAMILY_PROXIES)))
        update_tasks = self.task_pool.get_all_tasks()
        update_points = set((str(t.point) for t in update_tasks))
        self.ws_data_mgr.update_task_proxies(update_tasks)
        self.ws_data_mgr.update_family_proxies(update_points)
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
        WsDataMgr task_proxies."""
        self.ws_data_mgr.generate_definition_elements()
        self.ws_data_mgr.increment_graph_elements()
        self.assertEqual(0, len(self._collect_states(TASK_PROXIES)))
        update_tasks = self.task_pool.get_all_tasks()
        self.ws_data_mgr.update_task_proxies(update_tasks)
        self.assertTrue(len(update_tasks) > 0)
        self.assertEqual(
            len(update_tasks), len(self._collect_states(TASK_PROXIES)))

    def test_update_workflow(self):
        """Test method that updates the dynamic fields of the workflow msg."""
        self.ws_data_mgr.generate_definition_elements()
        old_time = self.data[WORKFLOW].last_updated
        self.ws_data_mgr.update_workflow()
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
