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
"""Test the client module components."""

from threading import Barrier
from time import sleep
from unittest import main

import zmq

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network.server import SuiteRuntimeServer, PB_METHOD_MAP
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.tests.network.key_setup import setup_keys
from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.data_store_mgr import DataStoreMgr


SERVER_CONTEXT = zmq.Context()


class TestSuiteRuntimeClient(CylcWorkflowTestCase):
    """Test the workflow runtime client."""

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
        super(TestSuiteRuntimeClient, self).setUp()
        self.scheduler.data_store_mgr = DataStoreMgr(self.scheduler)
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
            assert warnings == 0
        self.task_pool.release_runahead_tasks()
        self.scheduler.data_store_mgr.initiate_data_model()
        self.workflow_id = self.scheduler.data_store_mgr.workflow_id
        setup_keys(self.suite_name)
        barrier = Barrier(2, timeout=20)
        self.server = SuiteRuntimeServer(
            self.scheduler,
            context=SERVER_CONTEXT,
            threaded=True,
            barrier=barrier,
            daemon=True)
        port_range = glbl_cfg().get(['suite servers', 'run ports'])
        self.server.start(port_range[0], port_range[-1])
        # barrier.wait() doesn't seem to work properly here
        # so this workaround will do
        while barrier.n_waiting < 1:
            sleep(0.2)
        barrier.wait()
        sleep(0.5)
        self.client = SuiteRuntimeClient(
            self.scheduler.suite,
            host=self.scheduler.host,
            port=self.server.port)
        sleep(0.5)

    def tearDown(self):
        self.server.stop()
        self.client.stop()

    def test_constructor(self):
        self.assertFalse(self.client.socket.closed)

    def test_serial_request(self):
        """Test GraphQL endpoint method."""
        request_string = f'''
query {{
  workflows(ids: ["{self.workflow_id}"]) {{
    id
  }}
}}
'''

        data = self.client.serial_request(
            'graphql',
            args={'request_string': request_string})
        self.assertEqual(data['workflows'][0]['id'], self.workflow_id)
        pb_msg = self.client.serial_request('pb_entire_workflow')
        pb_data = PB_METHOD_MAP['pb_entire_workflow']()
        pb_data.ParseFromString(pb_msg)
        self.assertEqual(pb_data.workflow.id, self.workflow_id)


if __name__ == '__main__':
    main()
