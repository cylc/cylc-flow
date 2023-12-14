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

async def test_fail(flow, scheduler, run, reflog, complete, validate):
    """Test triggering on :fail"""
    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'true'
        },
        'scheduling': {
            'graph': {
                'R1': 'foo:failed => bar'
            }
        },
        'runtime': {
            'root': {
                'simulation': {'default run length': 'PT0S'}
            },
            'foo': {
                'simulation': {'fail cycle points': 'all'}
            }
        }
    })
    schd = scheduler(id_, paused_start=False)

    async with run(schd):
        triggers = reflog(schd)
        await complete(schd)

    assert triggers == {
        ('1/foo', None),
        ('1/bar', ('1/foo',)),
    }
