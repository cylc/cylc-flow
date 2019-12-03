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

"""Test abstract ZMQ interface."""
import random
from tempfile import TemporaryDirectory, NamedTemporaryFile
from threading import Barrier
from time import sleep

import pytest
import zmq

from cylc.flow.exceptions import ClientError, CylcError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network import ZMQSocketBase
from cylc.flow.suite_files import create_auth_files


def get_port_range():
    """Return global config port range."""
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()
HOST = "127.0.0.1"


def test_server_requires_valid_keys():
    """Server should not be able to connect to host/port without valid keys."""

    with TemporaryDirectory() as keys, NamedTemporaryFile(dir=keys) as fake:
        # Assign a blank file masquerading as a CurveZMQ certificate
        server = ZMQSocketBase(zmq.REQ, bind=True, daemon=True)

        with pytest.raises(ValueError, match=r"No public key found in "):
            server.start(*PORT_RANGE, private_key_location=fake.name)

        server.stop()


def test_client_requires_valid_keys():
    """Client should not be able to connect to host/port without valid keys."""
    with TemporaryDirectory() as keys, NamedTemporaryFile(dir=keys) as fake:
        port = random.choice(PORT_RANGE)
        client = ZMQSocketBase(zmq.REP)

        with pytest.raises(
                ClientError, match=r"Failed to load the suite's public "
                "key, so cannot connect."):
            # Assign a blank file masquerading as a CurveZMQ certificate
            client.start(HOST, port, srv_public_key_loc=fake.name)


def test_single_port():
    """Test server on a single port and port in use exception."""
    context = zmq.Context()
    create_auth_files('test_zmq')  # auth keys are required for comms
    serv1 = ZMQSocketBase(
        zmq.REP, context=context, suite='test_zmq', bind=True)
    serv2 = ZMQSocketBase(
        zmq.REP, context=context, suite='test_zmq', bind=True)

    serv1._socket_bind(*PORT_RANGE)
    port = serv1.port

    with pytest.raises(CylcError, match=r"Address already in use") as exc:
        serv2._socket_bind(port, port)

    serv2.stop()
    serv1.stop()
    context.destroy()


def test_start():
    """Test socket start."""
    create_auth_files('test_zmq_start')  # auth keys are required for comms
    barrier = Barrier(2, timeout=20)
    publisher = ZMQSocketBase(zmq.PUB, suite='test_zmq_start', bind=True,
                              barrier=barrier, threaded=True, daemon=True)
    assert publisher.barrier.n_waiting == 0
    assert publisher.loop is None
    assert publisher.port is None
    publisher.start(*PORT_RANGE)
    # barrier.wait() doesn't seem to work properly here
    # so this workaround will do
    while publisher.barrier.n_waiting < 1:
        sleep(0.2)
    assert barrier.wait() == 1
    assert publisher.loop is not None
    assert publisher.port is not None
    publisher.stop()


def test_stop():
    """Test socket/thread stop."""
    create_auth_files('test_zmq_stop')  # auth keys are required for comms
    barrier = Barrier(2, timeout=20)
    publisher = ZMQSocketBase(zmq.PUB, suite='test_zmq_stop', bind=True,
                              barrier=barrier, threaded=True, daemon=True)
    publisher.start(*PORT_RANGE)
    # barrier.wait() doesn't seem to work properly here
    # so this workaround will do
    while publisher.barrier.n_waiting < 1:
        sleep(0.2)
    barrier.wait()
    assert not publisher.socket.closed
    assert publisher.thread.is_alive()
    publisher.stop()
    assert publisher.socket.closed
    assert not publisher.thread.is_alive()


def test_client_server_connection_requires_consistent_keys():
    """Client-server connection must be blocked without consistent keys.

       Bodge a certificate to change the key, which must prevent connection."""
    pass  # TODO? Or is this tested via other tests?


# TODO: check connections & sockets are being stopped & cleaned up properly
