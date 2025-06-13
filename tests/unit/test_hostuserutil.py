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

import os
import re
from secrets import token_hex
import socket
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock

import pytest

from cylc.flow.hostuserutil import (
    HostUtil,
    get_fqdn_by_host,
    get_host,
    get_host_ip_by_name,
    get_user,
    get_user_home,
    is_remote_host,
    is_remote_user,
)


LOCALHOST_ALIASES = socket.gethostbyname_ex('localhost')[1]


@pytest.fixture
def mock_socket(monkeypatch: pytest.MonkeyPatch):
    """Reference implementation of socket functions, with some of their real
    observed quirks.

    Yes, it is horribly quirky. It is based on one linux system, and other
    systems or different /etc/hosts setup will result in different behaviour.
    """
    this_name = 'NCC1701'
    this_fqdn = f'{this_name}.starfleet.gov'
    this_ip = '12.345.67.89'
    this_ex = (this_fqdn, [this_name], [this_ip])

    localhost = 'localhost'
    localhost_fqdn = f'{localhost}.localdomain'
    localhost_ip = '127.0.0.1'
    localhost_aliases_v4 = [
        localhost_fqdn,
        f'{localhost}4',
        f'{localhost}4.localdomain4',
    ]
    localhost_aliases_v6 = [
        localhost_fqdn,
        f'{localhost}6',
        f'{localhost}6.localdomain6',
    ]
    localhost_ex = (
        localhost,
        [*localhost_aliases_v4, *localhost_aliases_v6],
        [localhost_ip, localhost_ip],
    )

    def _getfqdn(x: Optional[str] = None):
        if x:
            x = x.lower()
        if not x or this_fqdn.lower().startswith(x) or x == this_ip:
            return this_fqdn
        if x in {localhost, localhost_fqdn, localhost_ip}:
            return localhost_fqdn
        return x

    def _gethostbyaddr(x: str):
        x = x.lower()
        if this_fqdn.lower().startswith(x) or x == this_ip:
            return this_ex
        if x in {localhost, localhost_fqdn, '::1', *localhost_aliases_v6}:
            return (localhost, localhost_aliases_v6, ['::1'])
        if x in {localhost_ip, *localhost_aliases_v4}:
            return (localhost, localhost_aliases_v4, [localhost_ip])
        raise socket.gaierror("oopsie")

    def _gethostbyname_ex(x: str):
        x = x.lower()
        if x in {this_fqdn.lower(), this_name.lower()}:
            return this_ex
        if this_fqdn.lower().startswith(x):
            return (this_fqdn, [], [this_ip])
        if x in {localhost, localhost_fqdn}:
            return localhost_ex
        if x in localhost_aliases_v6:
            return (localhost, localhost_aliases_v6, ['::1'])
        if x in localhost_aliases_v4:
            return (localhost, localhost_aliases_v4, [localhost_ip])
        raise socket.gaierror("oopsie")

    mock_getfqdn = Mock(side_effect=_getfqdn)
    monkeypatch.setattr('cylc.flow.hostuserutil.socket.getfqdn', mock_getfqdn)
    mock_gethostbyaddr = Mock(side_effect=_gethostbyaddr)
    monkeypatch.setattr(
        'cylc.flow.hostuserutil.socket.gethostbyaddr', mock_gethostbyaddr
    )
    mock_gethostbyname_ex = Mock(side_effect=_gethostbyname_ex)
    monkeypatch.setattr(
        'cylc.flow.hostuserutil.socket.gethostbyname_ex', mock_gethostbyname_ex
    )
    return SimpleNamespace(
        this_fqdn=this_fqdn,
        this_ip=this_ip,
        this_ex=this_ex,
        localhost_ex=localhost_ex,
        getfqdn=mock_getfqdn,
        gethostbyaddr=mock_gethostbyaddr,
        gethostbyname_ex=mock_gethostbyname_ex,
    )


def test_is_remote_user_on_current_user():
    """is_remote_user with current user."""
    assert not is_remote_user(None)
    assert not is_remote_user(os.getenv('USER'))


@pytest.mark.parametrize(
    'host',
    [
        None,
        'localhost',
        pytest.param(os.getenv('HOSTNAME'), id="HOSTNAME-env-var"),
        pytest.param(get_host(), id="get_host()"),
        pytest.param(get_host_ip_by_name('localhost'), id="localhost-ip"),
        pytest.param(get_host_ip_by_name(get_host()), id="get_host-ip"),
        *LOCALHOST_ALIASES,
    ],
)
def test_is_remote_host__localhost(host):
    """is_remote_host with localhost."""
    assert not is_remote_host(host)


def test_get_fqdn_by_host_on_bad_host():
    """get_fqdn_by_host bad host.

    Warning:
        This test can fail due to ISP/network configuration
        (for example ISP may reroute failed DNS to custom search page)
        e.g: https://www.virginmedia.com/help/advanced-network-error-search

    """
    bad_host = 'nosuchhost.nosuchdomain.org'
    with pytest.raises(IOError) as exc:
        get_fqdn_by_host(bad_host)
    assert re.match(
        r"(\[Errno -2\] Name or service|"
        r"\[Errno 8\] nodename nor servname provided, or)"
        r" not known: '{}'".format(bad_host),
        str(exc.value)
    )
    assert exc.value.filename == bad_host


def test_get_user():
    """get_user."""
    assert os.getenv('USER') == get_user()


def test_get_user_home():
    """get_user_home."""
    assert os.getenv('HOME') == get_user_home()


def test_get_host_info__basic():
    hu = HostUtil(expire=3600)
    assert hu._get_host_info() == socket.gethostbyname_ex(socket.getfqdn())
    # Check it handles IP address:
    ip = get_host_ip_by_name('localhost')
    assert hu._get_host_info(ip) == socket.gethostbyname_ex('localhost')
    # Check raised exception for bad host:
    bad_host = f'nonexist{token_hex(8)}.com'
    with pytest.raises(IOError) as exc:
        hu._get_host_info(bad_host)
    assert bad_host in str(exc.value)


def test_get_host_info__advanced(mock_socket):
    hu = HostUtil(expire=3600)
    assert mock_socket.gethostbyname_ex.call_count == 0
    assert hu._get_host_info() == mock_socket.this_ex
    assert mock_socket.gethostbyname_ex.call_count == 1
    # Test caching:
    hu._get_host_info()
    assert mock_socket.gethostbyname_ex.call_count == 1
    # Test variations of host name:
    assert hu._get_host_info('NCC1701') == mock_socket.this_ex
    assert hu._get_host_info('ncc1701.starfleet') == mock_socket.this_ex
    # (Note:)
    assert (
        mock_socket.gethostbyname_ex('ncc1701.starfleet')
        != mock_socket.this_ex
    )
    assert hu._get_host_info('localhost4') == mock_socket.localhost_ex
    assert hu._get_host_info('localhost6') == mock_socket.localhost_ex
    # Test IP address:
    assert hu._get_host_info(mock_socket.this_ip) == mock_socket.this_ex
    assert hu._get_host_info('127.0.0.1') == mock_socket.localhost_ex
    # Test error:
    with pytest.raises(IOError):
        hu._get_host_info('nonexist')
    assert 'nonexist' not in hu._host_exs
