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

"""Tests for Broadcast Manager."""


async def test_reject_invalid_broadcast_is_remote_clash(
    one_conf, flow, start, scheduler, log_filter
):
    """`put_broadcast` gracefully rejects invalid broadcast:

    Existing config = [task][remote]host = foo
    Broadcast       = [task]platform = bar

    https://github.com/cylc/cylc-flow/issues/6693
    """
    conf = one_conf.copy()
    conf.update({'runtime': {'root': {'platform': 'foo'}}})
    wid = flow(conf)
    schd = scheduler(wid)
    async with start(schd):
        bc_mgr = schd.broadcast_mgr
        bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'remote': {'host': 'bar'}}]
        )
        assert log_filter(contains='Cannot apply broadcast')
