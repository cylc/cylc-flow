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
from unittest import main
from time import sleep

from cylc.flow import LOG
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.data_store_mgr import DataStoreMgr, DELTAS_MAP
from cylc.flow.network.publisher import WorkflowPublisher, serialize_data
from cylc.flow.network.subscriber import WorkflowSubscriber


def get_port_range():
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()


def test_serialize_data():
    str1 = 'hello'
    assert serialize_data(str1, None) == str1
    assert serialize_data(str1, 'encode', 'utf-8') == str1.encode('utf-8')
    assert serialize_data(str1, bytes, 'utf-8') == bytes(str1, 'utf-8')


class TestWorkflowPublisher(CylcWorkflowTestCase):

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
        super(TestWorkflowPublisher, self).setUp()
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
        self.publisher = WorkflowPublisher(
            self.suite_name, threaded=False, daemon=True)
        self.pub_data = self.scheduler.data_store_mgr.get_publish_deltas()

    def tearDown(self):
        self.publisher.stop()

    def test_constructor(self):
        self.assertFalse(self.publisher.threaded)
        self.assertIsNotNone(self.publisher.pattern)

    async def test_publish(self):
        """Test publishing data."""
        self.publisher.start(*PORT_RANGE)
        subscriber = WorkflowSubscriber(
            self.suite_name,
            host=self.scheduler.host,
            port=self.publisher.port,
            topics=[b'workflow'])
        # delay to allow subscriber to connection,
        # otherwise it misses the first message
        sleep(1.0)
        await self.publisher.publish(self.pub_data)
        btopic, msg = subscriber.loop.run_until_complete(
            subscriber.socket.recv_multipart())
        delta = DELTAS_MAP[btopic.decode('utf-8')]()
        delta.ParseFromString(msg)
        self.assertEqual(delta.id, self.workflow_id)
        subscriber.stop()
        with self.assertLogs(LOG, level='ERROR') as cm:
            asyncio.run(
                self.publisher.publish(None)
            )
        self.assertIn('publish: ', cm.output[0])

    def test_start(self):
        """Test publisher start."""
        self.assertIsNone(self.publisher.loop)
        self.assertIsNone(self.publisher.port)
        self.publisher.start(*PORT_RANGE)
        self.assertIsNotNone(self.publisher.loop)
        self.assertIsNotNone(self.publisher.port)
        self.publisher.stop()

    def test_stop(self):
        """Test publisher stop."""
        self.publisher.start(*PORT_RANGE)
        self.assertFalse(self.publisher.socket.closed)
        self.publisher.stop()
        self.assertTrue(self.publisher.socket.closed)


if __name__ == '__main__':
    main()
