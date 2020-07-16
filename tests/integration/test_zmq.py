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
from threading import Barrier

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
        zmq.REP, context=context, suite=myflow, bind=True)
    serv2 = ZMQSocketBase(
        zmq.REP, context=context, suite=myflow, bind=True)

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
    barrier = Barrier(2, timeout=20)
    publisher = ZMQSocketBase(zmq.PUB, suite=myflow, bind=True,
                              barrier=barrier, threaded=True, daemon=True)
    assert publisher.barrier.n_waiting == 0
    assert publisher.loop is None
    assert publisher.port is None
    publisher.start(*port_range)
    # barrier.wait() doesn't seem to work properly here
    # so this workaround will do
    while publisher.barrier.n_waiting < 1:
        sleep(0.2)
    assert barrier.wait() == 1
    assert publisher.loop is not None
    assert publisher.port is not None
    publisher.stop()


def test_stop(myflow, port_range):
    """Test socket/thread stop."""
    setup_keys(myflow)  # auth keys are required for comms
    barrier = Barrier(2, timeout=20)
    publisher = ZMQSocketBase(zmq.PUB, suite=myflow, bind=True,
                              barrier=barrier, threaded=True, daemon=True)
    publisher.start(*port_range)
    # barrier.wait() doesn't seem to work properly here
    # so this workaround will do
    while publisher.barrier.n_waiting < 1:
        sleep(0.1)
    barrier.wait()
    assert not publisher.socket.closed
    assert publisher.thread.is_alive()
    publisher.stop()
    assert publisher.socket.closed
    assert not publisher.thread.is_alive()
