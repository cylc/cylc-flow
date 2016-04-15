#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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

import re
from cycling.loader import get_interval, get_interval_cls
from task_trigger import get_message_offset


class MessageOutput(object):
    """
    A task message output.

    Used to generate an output string for a message trigger at a cycle point.

    TODO - these can be plain strings once the deprecated cycle point offset
    placeholders are removed from cylc (see GitHub #1761).

    """

    def __init__(self, msg, base_interval=None):
        self.msg = msg
        self.msg_offset = get_message_offset(msg, base_interval)

    def get_string(self, point):
        """Return the message string for this cycle point.

        Placeholders are replaced with the actual cycle point offset.

        """
        new_point = point
        if self.msg_offset:
            new_point = point + self.msg_offset
        return re.sub('\[.*\]', str(new_point), self.msg)

    def __eq__(self, other):
        return self.msg == other.msg and self.msg_offset == other.msg_offset
