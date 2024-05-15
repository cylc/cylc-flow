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

from time import sleep

import pytest

from cylc.flow.timer import Timer


def test_Timer(caplog: pytest.LogCaptureFixture):
    """Test the Timer class."""
    caplog.set_level('WARNING')
    timer = Timer("bob timeout", 1.0)

    # timer attributes
    assert timer.name == "bob timer"
    assert timer.interval == "PT1S"

    # start timer
    timer.reset()
    assert caplog.records[-1].message == "PT1S bob timer starts NOW"

    # check timeout
    sleep(2)
    assert timer.timed_out()
    assert caplog.records[-1].message == "bob timer timed out after PT1S"

    # stop should do nothing after timeout
    caplog.clear()
    timer.stop()
    assert not caplog.records

    # start timer again, then stop it
    timer.reset()
    assert caplog.records[-1].message == "PT1S bob timer starts NOW"
    timer.stop()
    assert caplog.records[-1].message == "bob timer stopped"

    # another stop should do nothing
    caplog.clear()
    timer.stop()
    assert not caplog.records
