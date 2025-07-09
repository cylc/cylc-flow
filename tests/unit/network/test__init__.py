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
"""Test __init__.py for network interfaces to Cylc scheduler objects."""

import pytest

import cylc.flow
from cylc.flow.exceptions import CylcVersionError
from cylc.flow.network import get_location
from cylc.flow.workflow_files import ContactFileFields


BASE_CONTACT_DATA = {
    ContactFileFields.HOST: 'foo',
    ContactFileFields.PORT: '42',
}


@pytest.fixture()
def mpatch_get_fqdn_by_host(monkeypatch):
    """Monkeypatch function used the same by all tests."""
    monkeypatch.setattr(
        cylc.flow.network, 'get_fqdn_by_host', lambda _: 'myhost.x.y.z'
    )


def test_get_location_ok(monkeypatch, mpatch_get_fqdn_by_host):
    """It passes when information is available."""
    contact_data = BASE_CONTACT_DATA.copy()
    contact_data[ContactFileFields.PUBLISH_PORT] = '8042'
    contact_data[ContactFileFields.VERSION] = cylc.flow.__version__
    monkeypatch.setattr(
        cylc.flow.network, 'load_contact_file', lambda _: contact_data
    )
    assert get_location('_') == (
        'myhost.x.y.z', 42, 8042, cylc.flow.__version__
    )


def test_get_location_old_contact_file(monkeypatch, mpatch_get_fqdn_by_host):
    """It Fails because it's not a Cylc 8 workflow."""
    contact_data = BASE_CONTACT_DATA.copy()
    contact_data['CYLC_SUITE_PUBLISH_PORT'] = '8042'
    contact_data['CYLC_VERSION'] = '5.1.2'
    monkeypatch.setattr(
        cylc.flow.network, 'load_contact_file', lambda _: contact_data
    )
    with pytest.raises(CylcVersionError, match=r'.*5.1.2.*'):
        get_location('_')
