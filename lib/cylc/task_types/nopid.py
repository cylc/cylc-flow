#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

class nopid(object):
    # NO PREVIOUS INSTANCE DEPENDENCE, FOR NON FORECAST MODELS

    def ready_to_spawn( self ):
        # Tasks with no previous instance dependence can in principle
        # spawn as soon as they are created, but this would result in
        # waiting tasks spawning out to the runahead limit. Spawning on
        # submission prevents this without preventing successive
        # instances of a task from running in parallel if the
        # opportunity arises. Tasks with no previous instance dependence
        # and no prerequisites will all go off at once out to the
        # runahead limit (unless they are clock-triggered tasks whose
        # time isn't up yet). These can be constrained with the
        # sequential attribute if necessary.
 
        if self.has_spawned():
            return False

        if self.state.is_submitted() or self.state.is_running() or \
                self.state.is_succeeded() or self.state.is_failed():
            # The tests for running or succeeded are probably not
            # necessary, but the test for failed will result in a
            # non-spawned task spawning when manually set to failed.
            return True
        else:
            return False
