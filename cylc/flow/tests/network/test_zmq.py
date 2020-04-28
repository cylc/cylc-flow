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

"""Test abstract ZMQ interface."""
import random
from shutil import rmtree
from tempfile import TemporaryDirectory, NamedTemporaryFile
from threading import Barrier
from time import sleep, time
from unittest.mock import MagicMock
import os

import pytest
import zmq

from cylc.flow.exceptions import ClientError, CylcError, SuiteServiceFileError
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.network import ZMQSocketBase
from cylc.flow.suite_files import (
    create_auth_files,
    get_suite_srv_dir,
    SuiteFiles,
    KeyInfo,
    KeyOwner,
    KeyType)


def get_port_range():
    """Return global config port range."""
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()
HOST = "127.0.0.1"


def test_server_cannot_start_when_server_private_key_cannot_be_loaded():
    """Server should not be able to start when its private key file
    cannot be opened."""
    server = ZMQSocketBase(
        zmq.REQ,
        suite=f"test_suite-{time()}",
        bind=True,
        daemon=True)

    with pytest.raises(
        SuiteServiceFileError,
        match=r"IO error opening server's private key from "
    ):
        server.start(*PORT_RANGE, srv_prv_key_loc="fake_dir/fake_location")

    server.stop()

# TODO test suite dir vs srv_prv_key_loc as arg to start


def test_server_cannot_start_when_certificate_file_only_contains_public_key():
    """Server should not be able to start when its certificate file does not
    contain the private key."""

    with TemporaryDirectory() as keys:
        pub, _priv = zmq.auth.create_certificates(keys, "server")

        server = ZMQSocketBase(zmq.REQ, bind=True, daemon=True)

        with pytest.raises(
            SuiteServiceFileError,
            match=r"Failed to find server's private key in "
        ):
            server.start(*PORT_RANGE, srv_prv_key_loc=pub)

        server.stop()


def test_server_cannot_start_when_public_key_not_found_in_certificate_file():
    """Server should not be able to start when its private key file does not
    contain the public key."""

    with TemporaryDirectory() as keys:
        priv_key_loc = os.path.join(keys, "server.key_secret")
        open(priv_key_loc, 'a').close()

        server = ZMQSocketBase(zmq.REQ, bind=True, daemon=True)

        with pytest.raises(
            SuiteServiceFileError,
            match=r"Failed to find server's public key in "
        ):
            server.start(*PORT_RANGE, srv_prv_key_loc=priv_key_loc)

        server.stop()


def test_client_requires_valid_server_public_key_in_private_key_file():
    """Client should not be able to connect to host/port without
    server public key."""
    suite_name = f"test_suite-{time()}"
    port = random.choice(PORT_RANGE)
    client = ZMQSocketBase(zmq.REP, suite=suite_name)

    test_suite_srv_dir = get_suite_srv_dir(reg=suite_name)
    key_info = KeyInfo(
        KeyType.PRIVATE,
        KeyOwner.CLIENT,
        suite_srv_dir=test_suite_srv_dir)
    directory = os.path.expanduser("~/cylc-run")
    tmpdir = os.path.join(directory, suite_name)
    os.makedirs(key_info.key_path, exist_ok=True)

    _pub, _priv = zmq.auth.create_certificates(key_info.key_path, "client")

    with pytest.raises(ClientError, match=r"Failed to load the suite's public "
                                          r"key, so cannot connect."):
        client.start(HOST, port, srv_public_key_loc="fake_location")

    client.stop()
    rmtree(tmpdir, ignore_errors=True)


def test_client_requires_valid_client_private_key():
    """Client should not be able to connect to host/port
    without client private key."""
    port = random.choice(PORT_RANGE)
    client = ZMQSocketBase(zmq.REP, suite=f"test_suite-{time()}")

    with pytest.raises(ClientError, match=r"Failed to find user's private "
                                          r"key, so cannot connect."):
        client.start(HOST, port, srv_public_key_loc="fake_location")

    client.stop()


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
