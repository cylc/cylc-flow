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
import pytest
import secrets

from cylc.flow.glbl_cfg_lazy import glbl_cfg
from cylc.flow.exceptions import CylcError
from cylc.flow.network.authentication import encrypt, decrypt
from cylc.flow.network.server import ZMQServer


def get_port_range():
    ports = glbl_cfg().get(['suite servers', 'run ports'])
    return min(ports), max(ports)


PORT_RANGE = get_port_range()
SECRET = str(secrets.SystemRandom().randint(10**0, 10**100))


def get_secret():
    return SECRET


def test_single_port():
    """Test server on a single port and port in use exception."""
    serv1 = ZMQServer(encrypt, decrypt, get_secret)
    serv2 = ZMQServer(encrypt, decrypt, get_secret)

    serv1.start(*PORT_RANGE)
    port = serv1.port

    with pytest.raises(CylcError, match=r"Address already in use") as exc:
        serv2.start(port, port)

    serv1.stop()
