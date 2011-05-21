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


import re

class nopid(object):
    # NO PREVIOUS INSTANCE DEPENDENCE, FOR NON FORECAST MODELS

    def ready_to_spawn( self ):
        # Tasks with no previous instance dependence can in principle
        # spawn as soon as they are created, but this results in
        # waiting tasks out to the maximum runahead, which clutters up
        # monitor views and carries some task processing overhead.
        # Abdicating instead when they start running prevents excess
        # waiting tasks without preventing instances from running in
        # parallel if the opportunity arises. BUT this does mean that a
        # failed or lame task's successor won't exist until the suite
        # operator gets the offender to spawn and die.

        # Note that tasks with no previous instance dependence and  NO
        # PREREQUISITES will all "go off at once" out to the runahead
        # limit (unless they are clock-triggered tasks whose time isn't
        # up yet). These can be constrained with the sequential
        # attribute if that is preferred. 
 
        if self.has_spawned():
            # already spawned
            return False

        if self.state.is_running() or self.state.is_succeeded():
            # see documentation above
            return True
        else:
            return False
