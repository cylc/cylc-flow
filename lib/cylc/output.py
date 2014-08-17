#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from cycling.loader import get_interval

# TODO - unify with RE in config.py
BACK_COMPAT_MSG_RE = re.compile('^(.*)\[\s*T\s*(([+-])\s*(\d+))?\s*\](.*)$')
MSG_RE = re.compile('^(.*)\[\s*(([+-])?\s*(.*))?\s*\](.*)$')

class output(object):
    """
    Hold and process task message outputs during suite configuration.
    
    This is for outputs used as outputs, not outputs used as prerequisites. The
    latter can have message and graph offsets, but these only have message
    offsets; they are always evaluated at the task's own cycle point.
    """

    def __init__(self, msg, base_interval=None):
        self.msg_offset = None
        self.msg = msg
        m = re.match(BACK_COMPAT_MSG_RE, self.msg)
        if m:
            # Old-style offset
            prefix, signed_offset, sign, offset, suffix = m.groups()
            # TODO - checked all signed offsets work
            self.msg_offset = base_interval.get_inferred_child(signed_offset)
        else:
            n = re.match(MSG_RE, msg)
            if n:
                # New-style offset
                prefix, signed_offset, sign, offset, suffix = n.groups()
                if offset:
                    self.msg_offset = get_interval(signed_offset)
                else:
                    self.msg_offset = get_interval_cls().get_null()
            else:
                # Plain message, no offset.
                pass

    def get( self, point ):
        new_point = point
        if self.msg_offset:
            new_point = point + self.msg_offset
        msg = re.sub( '\[.*\]', str(new_point), self.msg )
        return msg
