# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
"""Default fixtures for functional tests."""

from . import (
    run_dir,
    test_dir,
    flow_dir,
    make_flow,
    run_flow
)


import pytest


@pytest.fixture
def simple_flow(make_flow, run_flow):
    """A basic flow with one task."""
    foo = make_flow(
        'foo',
        {
            'scheduling': {
                'dependencies': {
                    'graph': 'foo'
                }
            }
        }
    )
    with run_flow(foo, hold_start=True) as stuff:
        yield stuff
