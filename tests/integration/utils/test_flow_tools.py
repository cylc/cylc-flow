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
"""Tests to ensure the tests are working - very meta.

https://github.com/cylc/cylc-flow/pull/2740#discussion_r206086008

"""

from pathlib import Path


# test _make_flow via the conftest fixture
def test_flow(run_dir, flow, one_conf):
    """It should create a flow in the run directory."""
    id_ = flow(one_conf)
    assert Path(run_dir / id_).exists()
    assert Path(run_dir / id_ / 'flow.cylc').exists()
    with open(Path(run_dir / id_ / 'flow.cylc'), 'r') as flow_file:
        assert 'scheduling' in flow_file.read()
