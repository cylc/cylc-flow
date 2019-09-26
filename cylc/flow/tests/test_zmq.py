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

from pathlib import Path
import pytest
from tempfile import TemporaryDirectory

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import CylcError
from cylc.flow.network.authentication import encode_, decode_
from cylc.flow.network.server import ZMQServer
from cylc.flow.suite_srv_files_mgr import SuiteSrvFilesManager


def get_port_range():
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()


def test_single_port():
    """Test server on a single port and port in use exception."""

    with TemporaryDirectory() as server_keys_parent_dir:

        # Create two temporary directories for holding the server keys.
        server_keys_dir_1 = os.path.join(
            server_keys_parent_dir, "server_keys_dir_1")
        server_keys_dir_2 = os.path.join(
            server_keys_parent_dir, "server_keys_dir_2")
        for keys_dir in (server_keys_dir_1, server_keys_dir_2):
            if not os.path.exists(keys_dir):
                os.makedirs(keys_dir)

        serv1 = ZMQServer(encode_, decode_)
        serv1.srv_files_mgr.SERVER_KEYS_PARENT_DIR = server_keys_dir_1
        serv2 = ZMQServer(encode_, decode_)
        serv2.srv_files_mgr.SERVER_KEYS_PARENT_DIR = server_keys_dir_2

        serv1.start(*PORT_RANGE)
        port = serv1.port

        with pytest.raises(
                CylcError, match=r"Address already in use") as exc:
            serv2.start(port, port)

        serv1.stop()
