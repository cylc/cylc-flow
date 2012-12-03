#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
    """For tasks with no previous instance dependence. These can in 
   principle spawn as soon as they are created, but that would result in
   waiting tasks spawning into the far future. Consequently we spawn on
   job submission; this prevents uncontrolled spawning but still allows
   successive instances to run in parallel if the opportunity arises. 
   
   Tasks that in principle have no previous instance dependence but
   which in practice cannot run in parallel with a previous instance
   (e.g. due to interference between temporary files) can be constrained
   with the sequential attribute if necessary (otherwise, imposing
   artificial dependence on the previous instance via prerequisites
   requires an associated cold-start task to get the suite started).

   A task can only fail after first being submitted, therefore a failed
   task should spawn if it hasn't already.
   
   Manually forcing a waiting task to the failed state will therefore
   result in it spawning (this is not the case for sequential tasks)."""

    def ready_to_spawn( self ):
 
        if self.has_spawned():
            return False

        if self.state.is_currently('submitted') or self.state.is_currently('running') or \
                self.state.is_currently('succeeded') or self.state.is_currently('failed'):
            return True
        else:
            return False

