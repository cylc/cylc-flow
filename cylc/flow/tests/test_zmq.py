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

import json
import os
import pytest
import random
import shutil
from tempfile import TemporaryDirectory, NamedTemporaryFile
import zmq
import zmq.auth

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import CylcError, ClientError
from cylc.flow.network.authentication import encode_, decode_
from cylc.flow.network.client import ZMQClient
from cylc.flow.network.server import ZMQServer
from cylc.flow.suite_files import (
    ensure_suite_keys_exist,
    ensure_user_keys_exist,
    UserFiles
)


def get_port_range():
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()
HOST = "127.0.0.1"


def test_server_requires_valid_keys():
    """Server should not be able to connect to host/port without valid keys."""

    with TemporaryDirectory() as keys, NamedTemporaryFile(dir=keys) as fake:
        # Assign a blank file masquerading as a CurveZMQ certificate
        server = ZMQServer(fake.name)

        with pytest.raises(ValueError, match=r"No public key found in "):
            server.start(*PORT_RANGE)

        try:  # in case the test fails such that the server did start
            server.stop()
        except Exception:
            pass


def test_client_requires_valid_keys():
    """Client should not be able to connect to host/port without valid keys."""
    with TemporaryDirectory() as keys, NamedTemporaryFile(dir=keys) as fake:
        port = random.choice(PORT_RANGE)

        with pytest.raises(
            ClientError, match=r"Failed to load the suite's public "
                "key, so cannot connect."):
            # Assign a blank file masquerading as a CurveZMQ certificate
            ZMQClient(HOST, port, fake.name)


def test_single_port():
    """Test server on a single port and port in use exception."""
    with TemporaryDirectory() as s_keys:
        _, servs_private_key = zmq.auth.create_certificates(s_keys, "servers")

        serv1 = ZMQServer(servs_private_key)
        serv2 = ZMQServer(servs_private_key)

        serv1.start(*PORT_RANGE)
        port = serv1.port
        with pytest.raises(
                CylcError, match=r"Address already in use") as exc:
            serv2.start(port, port)

        serv1.stop()


def test_client_server_connection_requires_consistent_keys():
    """Client-server connection must be blocked without consistent keys.

       Bodge a certificate to change the key, which must prevent connection."""
    pass  # TODO? Or is this tested via other tests?


# TODO: check connections & sockets are being stopped & cleaned up properly
