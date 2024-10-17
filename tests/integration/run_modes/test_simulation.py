# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.

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

"""Test the workings of simulation mode"""


async def test_started_trigger(flow, reftest, scheduler):
    """Does the started task output trigger downstream tasks
    in sim mode?

    Long standing Bug discovered in Skip Mode work.
    https://github.com/cylc/cylc-flow/pull/6039#issuecomment-2321147445
    """
    schd = scheduler(flow({
        'scheduler': {'events': {'stall timeout': 'PT0S', 'abort on stall timeout': True}},
        'scheduling': {'graph': {'R1': 'a:started => b'}}
    }), paused_start=False)
    assert await reftest(schd) == {
        ('1/a', None),
        ('1/b', ('1/a',))
    }
