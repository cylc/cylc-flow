"""Test the cylc.flow.host_select module with remote hosts.

NOTE: These tests require a remote host to work with and are skipped
      unless one is provided.

NOTE: These are functional tests, for unit tests see the docstrings in
      the host_select module.

"""
import socket

import pytest

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import HostSelectException
from cylc.flow.host_select import (
    select_host,
    select_suite_host
)
from cylc.flow.hostuserutil import get_fqdn_by_host


local_host, local_host_alises, _ = socket.gethostbyname_ex('localhost')
local_host_fqdn = get_fqdn_by_host(local_host)

remote_platform = glbl_cfg().get(
    ['test battery', 'remote platform with shared fs']
)
remote_platform_fqdn = None


if not remote_platform:
    pytest.skip('Remote test host not available', allow_module_level=True)
else:
    remote_platform_fqdn = get_fqdn_by_host(remote_platform)


def test_remote_select():
    """Test host selection works with remote host names."""
    assert select_host([remote_platform]) == (
        remote_platform, remote_platform_fqdn
    )


def test_remote_blacklict():
    """Test that blacklisting works with remote host names."""
    # blacklist by fqdn
    with pytest.raises(HostSelectException) as excinfo:
        select_host(
            [remote_platform],
            blacklist=[remote_platform]
        )
    # blacklist by short name
    with pytest.raises(HostSelectException) as excinfo:
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
    """Test that ranking evaluation works on remote hosts (via SSH)."""
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
        return (
            {f'{local_host_fqdn}': {('cpu_count',): 123}},
            {}
        )
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


def test_remote_suite_host_select(mock_glbl_cfg):
    """test [suite servers]run hosts"""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [suite servers]
                run hosts = {remote_platform}
        '''
    )
    assert select_suite_host() == (remote_platform, remote_platform_fqdn)


def test_remote_suite_host_condemned(mock_glbl_cfg):
    """test [suite servers]condemned hosts"""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [suite servers]
                run hosts = {remote_platform}, {local_host}
                condemned hosts = {remote_platform}
        '''
    )
    for _ in range(10):
        assert select_suite_host() == (local_host, local_host_fqdn)


def test_remote_suite_host_rankings(mock_glbl_cfg):
    """test [suite servers]rankings"""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [suite servers]
                run hosts = {remote_platform}
                ranking = """
                    # if this test fails due to race conditions
                    # then you are very lucky
                    virtual_memory().available > 123456789123456789
                    getloadavg()[0] < 1
                    cpu_count() > 512
                    disk_usage('/').free > 123456789123456789
                """
        '''
    )
    with pytest.raises(HostSelectException) as excinfo:
        select_suite_host()
    # ensure that host selection actually evuluated rankings
    assert set(excinfo.value.data[remote_platform_fqdn]) == {
        'virtual_memory().available > 123456789123456789',
        'getloadavg()[0] < 1',
        'cpu_count() > 512',
        "disk_usage('/').free > 123456789123456789"
    }
    # ensure that none of the rankings passed
    assert not any(excinfo.value.data[remote_platform_fqdn].values())
