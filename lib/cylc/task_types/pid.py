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

class pid(object):
    # PREVIOUS INSTANCE DEPENDENCE FOR WARM CYCLING FORECAST MODELS
    # which depend on a previous instance via restart files. These
    # don't spawn immediately on submission, they must wait until the
    # final restart output is completed, otherwise the spawned task
    # could trigger off the restart outputs of an earlier previous
    # instance (this should only happen if the suite operator forces
    # spawning ahead to skip some cycles after a problem of some kind).
    is_pid = True

    def set_next_restart_completed( self ):
        if self.reject_if_failed( 'set_next_restart_completed' ):
            return
        restart_messages = []
        for message in self.outputs.completed:
            if re.search( 'restart files ready for', message ):
                restart_messages.append( message )
        restart_messages.sort()
        for message in restart_messages:
            if not self.outputs.is_completed( message ):
                self.incoming( 'NORMAL', message )
                # that's the next one, quit now.
                break

    def set_all_restarts_completed( self ):
        if self.reject_if_failed( 'set_all_restarts_completed' ):
            return
        self.log( 'WARNING', 'setting ALL restart outputs completed' )
        for message in self.outputs.completed:
            if re.search( 'restart files ready for', message ):
                if not self.outputs.is_completed( message ):
                    self.incoming( 'NORMAL', message )
 
    def ready_to_spawn( self ):
        if self.has_spawned():
            return False

        if self.state.is_waiting():
            # Never spawn a waiting task type - the successor's restart
            # prerequisites could get satisfied by the later restart
            # outputs of an earlier previous instance, and thereby start
            # too soon (we want this to happen ONLY if the previous task
            # fails and is subsequently made to spawn and die by the
            # suite operator).
            return False

        if self.state.is_succeeded():
            # Always spawn succeeded tasks (probably unnecessary, they
            # will have spawned already).
            return True

        ready = False
        if self.state.is_running() or self.state.is_failed(): 
            # Failed tasks were necessarily running before failure, so
            # they will have spawned already, or not, according to
            # whether they failed before or after completing their
            # restart outputs.  So, like running tasks, ready only if
            # all restart outputs have been completed.
            ready = True
            for message in self.outputs.completed:
                if re.search( 'restart', message ) and \
                        not self.outputs.is_completed( message ):
                    ready = False
                    break
        return ready

    def my_successor_still_needs_me( self, tasks ):
        # TO DO: THIS IS NO LONGER (OR NEVER WAS?) USED?
        my_ct = self.c_time
        nx_ct = self.next_c_time()
        my_name = self.name
        for task in tasks:
            if task.name != my_name:
                continue
            if task.c_time != nx_ct:
                continue
            # found my successor
            if task.state.is_succeeded():
                return False
            else:
                return True

        # TO DO: consider, and observe, if this can ever happen: 
        print "WARNING: FAILED TO FIND THE SUCCESSOR OF A SPAWNED TASK!"
        return False
