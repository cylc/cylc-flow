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

"""Test the cylc.flow.host_select module with hosts.

NOTE: These tests require a remote host to work with and are skipped
      unless one is provided.

NOTE: These are functional tests, for unit tests see the docstrings in
      the host_select module.

"""
from shlex import quote
import socket
from subprocess import call, DEVNULL

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import HostSelectException
from cylc.flow.host_select import (
    select_host,
    select_workflow_host
)
from cylc.flow.hostuserutil import get_fqdn_by_host


local_host, local_host_alises, _ = socket.gethostbyname_ex('localhost')
local_host_fqdn = get_fqdn_by_host(local_host)


try:
    # get a suitable remote host for running tests on
    # NOTE: do NOT copy this testing approach in other python tests
    remote_platform = glbl_cfg().get(
        ['platforms', '_remote_background_shared_tcp', 'hosts'],
        []
    )[0]
    # don't run tests unless host is contactable
    if call(
        ['ssh', quote(remote_platform), 'hostname'],
        stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL
    ):
        raise KeyError('remote platform')
    # get the fqdn for this host
    remote_platform_fqdn = get_fqdn_by_host(remote_platform)
except (KeyError, IndexError):
    pytest.skip('Remote test host not available', allow_module_level=True)
    remote_platform = None


def test_remote_select():
    """Test host selection works with remote host names."""
    assert select_host([remote_platform]) == (
        remote_platform, remote_platform_fqdn
    )


def test_remote_blacklict():
    """Test that blacklisting works with remote host names."""
    # blacklist by fqdn
    with pytest.raises(HostSelectException):
        select_host(
            [remote_platform],
            blacklist=[remote_platform]
        )
    # blacklist by short name
    with pytest.raises(HostSelectException):
        select_host(
            [remote_platform],
            blacklist=[remote_platform_fqdn]
        )
    # make extra sure filters are really being applied
    for _ in range(10):
        assert select_host(
            [remote_platform, local_host],
            blacklist=[remote_platform]
        ) == (local_host, local_host_fqdn)


def test_remote_rankings():
    """Test that ranking evaluation works on hosts (via SSH)."""
    assert select_host(
        [remote_platform],
        ranking_string='''
            # if this test fails due to race conditions
            # then you have bigger issues than a test failure
            virtual_memory().available > 1
            getloadavg()[0] < 500
            cpu_count() > 1
            disk_usage('/').free > 1
        '''
    ) == (remote_platform, remote_platform_fqdn)


def test_remote_exclude(monkeypatch):
    """Ensure that hosts get excluded if they don't meet the rankings.

    Already tested elsewhere but this double-checks that it works if more
    than one host is provided to choose from."""
    def mocked_get_metrics(hosts, metrics, _=None):
        # pretend that ssh to remote_platform failed
        return {f'{local_host_fqdn}': {('cpu_count',): 123}}
    monkeypatch.setattr(
        'cylc.flow.host_select._get_metrics',
        mocked_get_metrics
    )
    assert select_host(
        [local_host, remote_platform],
        ranking_string='''
            cpu_count()
        '''
    ) == (local_host, local_host_fqdn)


def test_remote_workflow_host_select(mock_glbl_cfg):
    """test [scheduler][run hosts]available"""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [scheduler]
                [[run hosts]]
                    available = {remote_platform}
        '''
    )
    assert select_workflow_host() == (remote_platform, remote_platform_fqdn)


def test_remote_workflow_host_condemned(mock_glbl_cfg):
    """test [scheduler][run hosts]condemned hosts"""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [scheduler]
                [[run hosts]]
                    available = {remote_platform}, {local_host}
                    condemned = {remote_platform}
        '''
    )
    for _ in range(10):
        assert select_workflow_host() == (local_host, local_host_fqdn)


def test_remote_workflow_host_rankings(mock_glbl_cfg):
    """test [scheduler][run hosts]rankings"""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [scheduler]
                [[run hosts]]
                    available = {remote_platform}
                    ranking = """
                        # if this test fails due to race conditions
                        # then you are very lucky
                        virtual_memory().available > 123456789123456789
                        cpu_count() > 512
                        disk_usage('/').free > 123456789123456789
                    """
        '''
    )
    with pytest.raises(HostSelectException) as excinfo:
        select_workflow_host()
    # ensure that host selection actually evaluated rankings
    assert set(excinfo.value.data[remote_platform_fqdn]) - {'returncode'} == {
        'virtual_memory().available > 123456789123456789',
        'cpu_count() > 512',
        "disk_usage('/').free > 123456789123456789"
    }
    # ensure that none of the rankings passed
    assert not any(excinfo.value.data[remote_platform_fqdn].values())
