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
"""Test subsciber module components."""

import asyncio
from unittest import main
from time import sleep

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.tests.util import CylcWorkflowTestCase, create_task_proxy
from cylc.flow.data_store_mgr import DataStoreMgr
from cylc.flow.network.publisher import WorkflowPublisher
from cylc.flow.network.subscriber import WorkflowSubscriber, process_delta_msg


def get_port_range():
    """Fetch global config port range."""
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()


def test_process_delta_msg():
    """Test delta message processing."""
    # test non-key
    not_topic, not_delta = process_delta_msg(b'foo', b'bar', None)
    assert not_topic == 'foo'
    assert not_delta == b'bar'


class TestWorkflowSubscriber(CylcWorkflowTestCase):
    """Test the subscriber class components."""

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
        super(TestWorkflowSubscriber, self).setUp()
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
        self.publisher = WorkflowPublisher(
            self.suite_name, threaded=False, daemon=True)
        self.publisher.start(*PORT_RANGE)
        self.subscriber = WorkflowSubscriber(
            self.suite_name,
            host=self.scheduler.host,
            port=self.publisher.port,
            topics=[b'workflow'])
        # delay to allow subscriber to connection,
        # otherwise it misses the first message
        sleep(1.0)
        self.topic = None
        self.data = None

    def tearDown(self):
        self.subscriber.stop()
        self.publisher.stop()

    def test_constructor(self):
        """Test class constructor result."""
        self.assertIsNotNone(self.subscriber.context)
        self.assertFalse(self.subscriber.socket.closed)

    def test_subscribe(self):
        """Test publishing data."""
        pub_data = self.scheduler.data_store_mgr.get_publish_deltas()
        asyncio.run(
            self.publisher.publish(pub_data)
        )

        def msg_process(btopic, msg):
            self.subscriber.stopping = True
            self.topic, self.data = process_delta_msg(btopic, msg, None)
        self.subscriber.loop.run_until_complete(
            self.subscriber.subscribe(msg_process))
        self.assertEqual(self.data.id, self.workflow_id)


if __name__ == '__main__':
    main()
