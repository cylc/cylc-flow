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

import Pyro.core
from Queue import Queue

class msgqueue( Pyro.core.ObjBase ):
    """Pyro-connected class to queue incoming task messages"""

    def __init__( self ):
        Pyro.core.ObjBase.__init__(self)
        self.queue = Queue()

    def put( self, priority, message ):
        res = ( True, 'Message queued' )
        # TODO - check for legal logging priority?
        # queue incoming messages for this task
        self.queue.put( (priority, message) )
        return res

    def get_queue( self ):
        return self.queue

