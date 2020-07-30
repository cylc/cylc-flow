"""Test the cylc.flow.host_select module.

NOTE: these are functional tests, for unit tests see the docstrings in
      the host_select module.

"""
import socket

import pytest

from cylc.flow.exceptions import HostSelectException
from cylc.flow.host_select import (
    select_host,
    select_suite_host
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.parsec.exceptions import ListValueError


localhost, localhost_aliases, _ = socket.gethostbyname_ex('localhost')
localhost_fqdn = get_fqdn_by_host(localhost)


# NOTE: ensure that all localhost aliases are actually alises of localhost,
#       it would appear that this is not always the case
#       on Travis-CI on of the alises has a different fqdn from the fqdn
#       of the host it is an alias of
localhost_aliases = [
    alias
    for alias in localhost_aliases
    if get_fqdn_by_host(alias) == localhost_fqdn
]


def test_localhost():
    """Basic test with one host to choose from."""
    assert select_host([localhost]) == (
        localhost,
        localhost_fqdn
    )


def test_unique():
    """Basic test choosing from multiple forms of localhost"""
    name, fqdn = select_host(
        localhost_aliases + [localhost]
    )
    assert name in localhost_aliases + [localhost]
    assert fqdn == localhost_fqdn


def test_filter():
    """Test that hosts are filtered out if specified."""
    message = 'Localhost not allowed'
    with pytest.raises(HostSelectException) as excinfo:
        select_host(
            [localhost],
            blacklist=[localhost],
            blacklist_name='Localhost not allowed'
        )
    assert message in str(excinfo.value)


def test_rankings():
    """Positive test that rankings are evaluated.

    (doesn't prove anything by itself hence test_unreasonable_rankings)
    """
    assert select_host(
        [localhost],
        ranking_string='''
            # if this test fails due to race conditions
            # then you have bigger issues than a test failure
            virtual_memory().available > 1
            getloadavg()[0] < 500
            cpu_count() > 1
            disk_usage('/').free > 1
        '''
    ) == (localhost, localhost_fqdn)


def test_unreasonable_rankings():
    """Negative test that rankings are evaluated.

    (doesn't prove anything by itself hence test_rankings)
    """
    with pytest.raises(HostSelectException) as excinfo:
        select_host(
            [localhost],
            ranking_string='''
                # if this test fails due to race conditions
                # then you are very lucky
                virtual_memory().available > 123456789123456789
                getloadavg()[0] < 1
                cpu_count() > 512
                disk_usage('/').free > 123456789123456789
            '''
        )
    assert (
        'virtual_memory().available > 123456789123456789: False'
    ) in str(excinfo.value)


def test_metric_command_failure():
    """If the psutil command (or SSH) fails ensure the host is excluded."""
    with pytest.raises(HostSelectException) as excinfo:
        select_host(
            [localhost],
            ranking_string='''
                # elephant is not a psutil attribute
                # so will cause the command to fail
                elephant
            '''
        )
    assert excinfo.value.data[localhost_fqdn]['get_metrics'] == (
        'Command failed (exit: 1)'
    )


def test_suite_host_select(mock_glbl_cfg):
    """Run the suite_host_select mechanism."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [suite servers]
                run hosts = {localhost}
        '''
    )
    assert select_suite_host() == (localhost, localhost_fqdn)


def test_suite_host_select_default(mock_glbl_cfg):
    """Ensure "localhost" is provided as a default host."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        '''
            [suite servers]
                run hosts =
        '''
    )
    hostname, host_fqdn = select_suite_host()
    assert hostname in localhost_aliases + [localhost]
    assert host_fqdn == localhost_fqdn


# NOTE: on Travis-CI the fqdn of `localhost` is `localhost`
@pytest.mark.skipif(
    localhost == localhost_fqdn,
    reason='Cannot condemn a host unless is has a safe unique fqdn.'
)
def test_suite_host_select_condemned(mock_glbl_cfg):
    """Ensure condemned hosts are filtered out."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [suite servers]
                run hosts = {localhost}
                condemned hosts = {localhost_fqdn}
        '''
    )
    with pytest.raises(HostSelectException) as excinfo:
        select_suite_host()
    assert 'blacklisted' in str(excinfo.value)
    assert 'condemned host' in str(excinfo.value)


def test_condemned_host_ambiguous(mock_glbl_cfg):
    """Test the [suite servers]condemend host coercer

    Not actually host_select code but related functionality.
    """
    with pytest.raises(ListValueError) as excinfo:
        mock_glbl_cfg(
            'cylc.flow.host_select.glbl_cfg',
            f'''
                [suite servers]
                    run hosts = {localhost}
                    condemned hosts = {localhost}
            '''
        )
    assert 'ambiguous host' in excinfo.value.msg
