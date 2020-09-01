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

"""Test validation of unicode rules and similar."""

from cylc.flow.unicode_rules import MessageTriggerValidator


def test_task_message_validation():
    """Test that `[runtime][<task>][outputs]<output> = msg` messages validate
    correctly."""
    tests = [
        ('Chronon Field Regulator', True),
        # Cannot have colon unless first part of message is logging
        # severity level:
        ('Time machine location: Bradbury Swimming Pool', False),
        # but after that colons are okay:
        ('INFO: Time machine location: Bradbury Swimming Pool', True),
        # simply poor form:
        ('Foo:', False),
        (':Foo', False),
        ('::group::', False)
    ]
    for task_message, expected in tests:
        valid, _ = MessageTriggerValidator.validate(task_message)
        assert valid is expected
