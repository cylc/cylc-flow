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

from textwrap import dedent

import pytest

from cylc.flow.exceptions import (
    CylcError,
    HostSelectException,
)


def test_cylc_error_str():
    error = CylcError("abcd")
    assert str(error) == "abcd"


def test_host_select_exception():
    """Test exception used for host selection failures.

    * Could not connect to hosts (e.g. SSH failure).
    * Commands failed (e.g. configuration error).
    * Could not obtain metrics (e.g. host ranking expression error).
    * No available hosts (e.g. no hosts met ranking thresholds).

    """
    # it should format the selection results nicely
    exc = HostSelectException(
        {
            'host-1': {'returncode': 1},
            'host-2': {'returncode': 1},
        },
        ranking='virtual_memory().available > 1',
    )
    assert str(exc) == dedent('''
        Could not select host from:
            host-1:
                returncode: 1
            host-2:
                returncode: 1
    ''').strip()


@pytest.mark.parametrize(
    'ret_code, expect',
    [
        # it should give a useful hint for exit code "2"
        # (error in the selection ranking expression)
        (2, 'This is likely an error in the ranking expression'),
        # it should give a useful hint for the exit code "255"
        # (ssh error)
        (255, 'Cylc could not establish SSH connection to the run hosts.')
    ]
)
def test_host_select_exception_returncodes(ret_code, expect):
    assert expect in str(
        HostSelectException(
            {
                'host-1': {'returncode': ret_code},
                'host-2': {'returncode': ret_code},
            },
            ranking='virtual_memory().available > 1',
        )
    )
