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


async def test_reject_valid_broadcast_is_remote_clash_with_config(
    one_conf, flow, start, scheduler, log_filter
):
    """`put_broadcast` gracefully rejects invalid broadcast:

    Existing config = [task][remote]host = foo
    Broadcast       = [task]platform = bar

    https://github.com/cylc/cylc-flow/issues/6693
    """
    one_conf.update({'runtime': {'root': {'platform': 'foo'}}})
    wid = flow(one_conf)
    schd = scheduler(wid)
    async with start(schd):
        bc_mgr = schd.broadcast_mgr
        good, bad = bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'remote': {'host': 'bar'}}]
        )

        # the error should be reported in the workflow log
        assert log_filter(contains='Cannot apply broadcast')
        assert bc_mgr.broadcasts == {'1': {}}

        # the bad setting should be reported
        assert good == []
        assert bad == {
            'settings': [
                {'remote': {'host': 'bar'}},
            ]
        }


async def test_reject_valid_broadcast_is_remote_clash_with_broadcast(
    one_conf, flow, start, scheduler, log_filter
):
    """`put_broadcast` gracefully rejects invalid broadcast:

    Existing Broadcast = [task][remote]host = foo
    New Broadcast      = [task]platform = bar

    https://github.com/cylc/cylc-flow/pull/6711/files#r2033457964
    """
    schd = scheduler(flow(one_conf))
    async with start(schd):
        bc_mgr = schd.broadcast_mgr
        _, bad = bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'remote': {'host': 'bar'}}]
        )
        assert bad == {}  # broadcast should be successful

        # this should not be allowed, if it is the scheduler will crash
        # when unpaused:
        good, bad = bc_mgr.put_broadcast(
            point_strings=['1'],
            namespaces=['one'],
            settings=[{'platform': 'foo'}]
        )

        # the error should be reported in the workflow log
        assert log_filter(contains='Cannot apply broadcast')
        assert bc_mgr.broadcasts == {'1': {'one': {'remote': {'host': 'bar'}}}}

        # the bad setting should be reported
        assert good == []
        assert bad == {
            'settings': [
                {'platform': 'foo'},
            ]
        }
