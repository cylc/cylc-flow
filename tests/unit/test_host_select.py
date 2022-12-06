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

"""Test the cylc.flow.host_select module.

NOTE: these are functional tests, for unit tests see the docstrings in
      the host_select module.

"""
import logging
import socket

import pytest

from cylc.flow import CYLC_LOG
from cylc.flow.exceptions import HostSelectException
from cylc.flow.host_select import (
    _get_metrics,
    select_host,
    select_workflow_host,
)
from cylc.flow.hostuserutil import get_fqdn_by_host
from cylc.flow.parsec.exceptions import ListValueError


localhost, localhost_aliases, _ = socket.gethostbyname_ex('localhost')
localhost_fqdn = get_fqdn_by_host(localhost)


# NOTE: ensure that all localhost aliases are actually aliases of localhost,
#       it would appear that this is not always the case
#       on Travis-CI on of the aliases has a different fqdn from the fqdn
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
    # we should expect the special (2) returncode
    # (i.e. the command ran fine but there was something wrong with the
    # provided expression)
    assert excinfo.value.data[localhost_fqdn]['returncode'] == 2


def test_workflow_host_select(mock_glbl_cfg):
    """Run the workflow_host_select mechanism."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [scheduler]
                [[run hosts]]
                    available= {localhost}
        '''
    )
    assert select_workflow_host() == (localhost, localhost_fqdn)


def test_workflow_host_select_default(mock_glbl_cfg):
    """Ensure "localhost" is provided as a default host."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        '''
            [scheduler]
                [[run hosts]]
                    available =
        '''
    )
    hostname, host_fqdn = select_workflow_host()
    assert hostname in localhost_aliases + [localhost]
    assert host_fqdn == localhost_fqdn


# NOTE: on Travis-CI the fqdn of `localhost` is `localhost`
@pytest.mark.skipif(
    localhost == localhost_fqdn,
    reason='Cannot condemn a host unless is has a safe unique fqdn.'
)
def test_workflow_host_select_condemned(mock_glbl_cfg):
    """Ensure condemned hosts are filtered out."""
    mock_glbl_cfg(
        'cylc.flow.host_select.glbl_cfg',
        f'''
            [scheduler]
                [[run hosts]]
                    available = {localhost}
                    condemned = {localhost_fqdn}
        '''
    )
    with pytest.raises(HostSelectException) as excinfo:
        select_workflow_host()
    assert 'blacklisted' in str(excinfo.value)
    assert 'condemned host' in str(excinfo.value)


def test_condemned_host_ambiguous(mock_glbl_cfg):
    """Test the [scheduler]condemend host coercer

    Not actually host_select code but related functionality.
    """
    with pytest.raises(ListValueError) as excinfo:
        mock_glbl_cfg(
            'cylc.flow.host_select.glbl_cfg',
            f'''
                [scheduler]
                    [[run hosts]]
                        available = {localhost}
                        condemned = {localhost}
            '''
        )
    assert 'ambiguous host' in excinfo.value.msg


def test_get_metrics_no_hosts_error(caplog):
    """It should handle SSH errors.

    If a host is not contactable then it should be shipped.
    """
    caplog.set_level(logging.WARN, CYLC_LOG)
    host_stats, data = _get_metrics(['not-a-host'], None)
    # a warning should be logged
    assert len(caplog.records) == 1
    # no data for the host should be returned
    assert not host_stats
    # the return code should be recorded
    assert data == {'not-a-host': {'returncode': 255}}
