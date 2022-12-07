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

import pytest

from cylc.flow.exceptions import NoHostsError
from cylc.flow.scripts.check_versions import check_versions


@pytest.fixture
def break_host_selection(monkeypatch):
    """Make host selection for any platform fail with NoHostsError."""
    def _get_host_from_platform(platform, *args, **kwargs):
        raise NoHostsError(platform)

    monkeypatch.setattr(
        'cylc.flow.scripts.check_versions.get_host_from_platform',
        _get_host_from_platform,
    )

    def _get_platform(platform_name, *args, **kwargs):
        return {'name': platform_name}

    monkeypatch.setattr(
        'cylc.flow.scripts.check_versions.get_platform',
        _get_platform,
    )


def test_no_hosts_error(break_host_selection, capsys):
    """It should handle NoHostsError events."""
    versions = check_versions(['buggered'], True)
    # the broken platform should be skipped (so no returned versions)
    assert not versions
    # a warning should have been logged to stderr
    out, err = capsys.readouterr()
    assert 'Could not connect to buggered' in err
