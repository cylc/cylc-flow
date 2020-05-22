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

from time import sleep

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network.publisher import WorkflowPublisher, serialize_data


@pytest.fixture(scope='session')
def port_range():
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


def test_serialize_data():
    str1 = 'hello'
    assert serialize_data(str1, None) == str1
    assert serialize_data(str1, 'encode', 'utf-8') == str1.encode('utf-8')
    assert serialize_data(str1, bytes, 'utf-8') == bytes(str1, 'utf-8')


def test_start_stop(port_range):
    pub = WorkflowPublisher('beef')
    assert not pub.loop
    pub.start(*port_range)
    sleep(1)  # TODO - remove this evil sleep
    assert not pub.socket.closed
    assert pub.loop
    pub.stop()
    assert pub.socket.closed
