"""Test abstract ZMQ interface."""
import pytest
import secrets

from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
from cylc.network import encrypt, decrypt
from cylc.network.server import ZMQServer


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

    with pytest.raises(CylcError) as exc:
        serv2.start(port, port)
    assert 'Address already in use' in str(exc)

    serv1.stop()
