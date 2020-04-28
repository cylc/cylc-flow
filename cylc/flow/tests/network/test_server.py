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

import asyncio
from threading import Barrier
from time import sleep
from unittest import main

import zmq

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network.authorisation import Priv
from cylc.flow.network.server import SuiteRuntimeServer, PB_METHOD_MAP
from cylc.flow.suite_files import create_auth_files
from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.data_store_mgr import DataStoreMgr


def get_port_range():
    """Fetch global config port range."""
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()
SERVER_CONTEXT = zmq.Context()


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
            assert 0 == warnings
        self.task_pool.release_runahead_tasks()
        self.scheduler.data_store_mgr.initiate_data_model()
        self.workflow_id = self.scheduler.data_store_mgr.workflow_id
        create_auth_files(self.suite_name)  # auth keys are required for comms
        barrier = Barrier(2, timeout=10)
        self.server = SuiteRuntimeServer(
            self.scheduler,
            context=SERVER_CONTEXT,
            threaded=True,
            barrier=barrier,
            daemon=True
        )
        self.server.public_priv = Priv.CONTROL
        self.server.start(*PORT_RANGE)
        # barrier.wait() doesn't seem to work properly here
        # so this workaround will do
        while barrier.n_waiting < 1:
            sleep(0.2)
        barrier.wait()
        sleep(0.5)

    def tearDown(self):
        self.server.stop()

    def test_constructor(self):
        self.assertFalse(self.server.socket.closed)
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
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        data = self.server.graphql(request_string)
        self.assertEqual(data['workflows'][0]['id'], self.workflow_id)

    def test_pb_data_elements(self):
        """Test Protobuf elements endpoint method."""
        element_type = 'workflow'
        data = PB_METHOD_MAP['pb_data_elements'][element_type]()
        data.ParseFromString(self.server.pb_data_elements(element_type))
        self.assertEqual(data.id, self.workflow_id)

    def test_pb_entire_workflow(self):
        """Test Protobuf entire workflow endpoint method."""
        data = PB_METHOD_MAP['pb_entire_workflow']()
        data.ParseFromString(self.server.pb_entire_workflow())
        self.assertEqual(data.workflow.id, self.workflow_id)

    def test_listener(self):
        """Test listener."""
        self.server.queue.put('STOP')
        sleep(2.0)
        self.server.queue.put('foobar')
        with self.assertRaises(ValueError):
            self.server._listener()

    def test_receiver(self):
        """Test receiver."""
        msg_in = {'not_command': 'foobar', 'args': {}}
        self.assertIn('error', self.server._receiver(msg_in))
        msg_in = {'command': 'foobar', 'args': {}}
        self.assertIn('error', self.server._receiver(msg_in))


if __name__ == '__main__':
    main()
