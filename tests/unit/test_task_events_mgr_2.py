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

from unittest.mock import Mock
import pytest


from cylc.flow.task_events_mgr import TaskEventsManager


@pytest.mark.parametrize(
    "broadcast, remote, platforms, expected",
    [
        ("hpc1", "a", "b", "hpc1"),
        (None, "hpc1", "b", "hpc1"),
        (None, None, "hpc1", "hpc1"),
        (None, None, None, None),
    ]
)
def test_get_remote_conf(broadcast, remote, platforms, expected):
    """Test TaskEventsManager._get_remote_conf()."""

    task_events_mgr = TaskEventsManager(
        None, None, None, None, None, None, None, None)

    task_events_mgr.broadcast_mgr = Mock(
        get_broadcast=lambda x: {
            "remote": {
                "host": broadcast
            }
        }
    )

    itask = Mock(
        identity='foo.1',
        tdef=Mock(
            rtconfig={
                'remote': {
                    'host': remote
                }
            }
        ),
        platform={
            'host': platforms
        }
    )

    assert task_events_mgr._get_remote_conf(itask, 'host') == expected


DEFAULT = [900]


@pytest.mark.parametrize(
    "broadcast, suite, platforms, expected",
    [
        ([800], [700], [600], [800]),
        (None, [700], [600], [700]),
        (None, None, [600], [600]),
        (None, None, None, DEFAULT),
    ]
)
def test_get_suite_platforms_conf(broadcast, suite, platforms, expected):
    """Test TaskEventsManager._get_polling_interval_conf()."""

    task_events_mgr = TaskEventsManager(
        None, None, None, None, None, None, None, None)

    KEY = "execution polling intervals"

    task_events_mgr.broadcast_mgr = Mock(
        get_broadcast=lambda x: {
            KEY: broadcast
        }
    )

    itask = Mock(
        identity='foo.1',
        tdef=Mock(
            rtconfig={
                KEY: suite
            }
        ),
        platform={
            KEY: platforms
        }
    )

    assert (
        task_events_mgr._get_suite_platforms_conf(itask, KEY, DEFAULT) ==
        expected
    )
