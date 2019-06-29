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
from cylc.flow.ws_data_mgr import WsDataMgr
from cylc.flow.network.authorisation import Priv
from cylc.flow.network.server import SuiteRuntimeServer


class TestSuiteRuntimeServer(CylcWorkflowTestCase):

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
        super(TestSuiteRuntimeServer, self).setUp()
        self.scheduler.ws_data_mgr = WsDataMgr(self.scheduler)
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
        self.scheduler.ws_data_mgr.initiate_data_model()
        self.workflow_id = self.scheduler.ws_data_mgr.workflow_id
        self.server = SuiteRuntimeServer(self.scheduler)
        self.server.public_priv = Priv.CONTROL

    def test_constructor(self):
        self.assertIsNotNone(self.server.schd)
        self.assertIsNotNone(self.server.resolvers)

    def test_graphql(self):
        """Test GraphQL endpoint method."""
        request_string = f'''
query {{
  workflows(ids: ["{self.workflow_id}"]) {{
    id
  }}
}}
'''
        data = self.server.graphql(request_string)
        self.assertEqual(data['workflows'][0]['id'], self.workflow_id)


if __name__ == '__main__':
    main()
