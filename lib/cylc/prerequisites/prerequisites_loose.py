#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
import sys
from plain_prerequisites import plain_prerequisites

# THIS IS USED WITH ASYNCHRONOUS TASKS (EXPERIMENTAL)

class loose_prerequisites( plain_prerequisites ):
    is_loose = True
    def __init__( self, owner_id ):
        self.match_group = {}
        plain_prerequisites.__init__( self, owner_id )

    def add( self, message ):
        # TODO - CHECK FOR LOOSE PATTERN HERE
        # see fuzzy_prerequisites for example
        plain_prerequisites.add( self, message )

    def sharpen_up( self, loose, sharp ):
        # replace a loose prerequisite with the actual output message
        # that satisfied it, and set it satisfied.
        lbl = self.labels[loose]
        self.messages[lbl] = sharp
        self.labels[sharp] = lbl
        del self.labels[loose]

    def satisfy_me( self, outputs ):
        # can any completed outputs satisfy any of my prerequisites?
        for label in self.satisfied:
            premsg = self.messages[label]
            for outmsg in outputs:
                if premsg == outmsg:
                    # (already done)
                    continue
                m = re.match( premsg, outmsg )
                if m:
                    # replace loose prereq with the actual output that satisfied it
                    #self.match_group[outmsg] = m.groups()[0]
                    self.asyncid = m.groups()[0]
                    self.sharpen_up( premsg, outmsg )
                    self.satisfied[ label ] = True
                    self.satisfied_by[ label ] = outputs[outmsg] # owner_id

    def dump( self ):
        return plain_prerequisites.dump(self)
