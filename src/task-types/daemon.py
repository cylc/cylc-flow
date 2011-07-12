#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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


from task import task
from oneoff import oneoff
import re

class daemon( oneoff, task ):
    # A one off task that dynamically and adds outputs as messages
    # matching registered patterns come in. The corresponding real task
    # may keep running indefinitely, e.g. to watch for incoming
    # asynchronous data.

    # note 'daemon' - hasattr(task, 'daemon') returns True for all tasks 
    # due to the pyro daemon (I think).
    daemon_task = True  

    def incoming( self, priority, message ):
        # intercept incoming messages and check for a pattern match 
        for pattern in self.output_patterns:
            if re.match( pattern, message ):
                self.outputs.add( message )
        task.incoming( self, priority, message )
