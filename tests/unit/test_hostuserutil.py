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
