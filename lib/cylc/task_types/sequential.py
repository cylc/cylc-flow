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

class sequential(object):
    """Force sequential behaviour in tasks that in principle do not
    depend on their own previous instance, but which in practice cannot
    run in parallel with previous instances (e.g. because of
    interference in use of temporary files) by spawning a successor
    only after the task succeeds. The alternative, to impose artificial
    previous instance dependence via prerequisites, requires an
    associated cold-start task to get the suite started. 

    Sequential tasks should only spawn on success, not failure;
    otherwise on restarting a suite with a failed sequential task in
    it, the failed task will be resubmitted and (other prerequisites
    allowing) so will its newly spawned successor, resulting in two
    instances running in parallel, which is exactly what we don't want
    sequential tasks to do.
    
    Manually forcing a waiting sequential task to the failed state will
    not result in it spawning, so if a sequential task fails and cannot
    be successfully re-run, you can either force it to the succeeded 
    state, force it to spawn, or insert a new instance in the next
    cycle."""

    def ready_to_spawn( self ):
        if self.has_spawned():
            return False
        if self.state.is_currently('succeeded'):
            return True

