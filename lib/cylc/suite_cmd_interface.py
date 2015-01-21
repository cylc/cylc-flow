#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import Pyro.core
from Queue import Queue

class comqueue( Pyro.core.ObjBase ):
    """Pyro-connected class to queue suite control requests."""

    def __init__( self, legal_commands=[] ):
        Pyro.core.ObjBase.__init__(self)
        self.legal = legal_commands
        self.queue = Queue()

    def put( self, command, *args ):
        res = ( True, 'Command queued' )
        if command not in self.legal:
            res = ( False, 'ERROR: Illegal command: ' + str(command) )
        else:
            # queue incoming messages for this task
            self.queue.put( (command, args) )
        return res

    def get_queue( self ):
        return self.queue
