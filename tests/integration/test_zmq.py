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

import pytest
import zmq

from cylc.flow.exceptions import CylcError
from cylc.flow.network import ZMQSocketBase

from .key_setup import setup_keys


@pytest.fixture(scope='module')
def myflow(mod_flow, mod_one_conf):
    return mod_flow(mod_one_conf)


def test_single_port(myflow, port_range):
    """Test server on a single port and port in use exception."""
    context = zmq.Context()
    setup_keys(myflow)  # auth keys are required for comms
    serv1 = ZMQSocketBase(
        zmq.REP, context=context, workflow=myflow, bind=True)
    serv2 = ZMQSocketBase(
        zmq.REP, context=context, workflow=myflow, bind=True)

    serv1._socket_bind(*port_range)
    port = serv1.port

    with pytest.raises(CylcError, match=r"Address already in use"):
        serv2._socket_bind(port, port)

    serv2.stop()
    serv1.stop()
    context.destroy()


def test_start(myflow, port_range):
    """Test socket start."""
    setup_keys(myflow)  # auth keys are required for comms
    publisher = ZMQSocketBase(zmq.PUB, workflow=myflow, bind=True)
    assert publisher.loop is None
    assert publisher.port is None
    publisher.start(*port_range)
    assert publisher.loop is not None
    assert publisher.port is not None
    publisher.stop()


def test_stop(myflow, port_range):
    """Test socket/thread stop."""
    setup_keys(myflow)  # auth keys are required for comms
    publisher = ZMQSocketBase(zmq.PUB, workflow=myflow, bind=True)
    publisher.start(*port_range)
    assert not publisher.socket.closed
    publisher.stop()
    assert publisher.socket.closed
