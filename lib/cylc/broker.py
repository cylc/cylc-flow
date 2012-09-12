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

import logging

# BROKER:
# A collection of output messages with associated owner ids (of the
# originating tasks) representing the outputs of ALL TASKS in the
# suite, and initialised from the outputs of all the tasks.
# "Satisfied" => the output has been completed.

class broker(object):
    # A broker aggregates output messages from many objects.
    # Each task registers its outputs with the suite broker, then each
    # task tries to get its prerequisites satisfied by the broker's
    # outputs.

    def __init__( self ):
         self.log = logging.getLogger( 'main' )
         self.all_outputs = {}   # all_outputs[ message ] = taskid

    def register( self, task ):
        # because task ids are unique, and all tasks register their
        # outputs anew in each dependency negotiation round, register 
        # should only be called once by each task

        owner_id = task.id
        outputs = task.outputs.completed

        if owner_id in self.all_outputs.keys():
            self.log.critical(  owner_id + "has already registered its outputs!" )
            self.log.critical( "(perhaps you inserted an already-spawned task?")
            raise SystemExit("ABORTING")

        self.all_outputs.update( outputs )

        # TO DO: SHOULD WE CHECK FOR SYSTEM-WIDE DUPLICATE OUTPUTS?
        # (note that successive tasks of the same type can register
        # identical outputs if they write staggered restart files).

    def reset( self ):
        # throw away all messages
        self.all_outputs = {}

    def dump( self ):
        # for debugging
        print "BROKER DUMP:"
        for msg in self.all_outputs:
            print " + " + self.all_outputs[msg], msg

    def negotiate( self, task ):
        # can my outputs satisfy any of task's prerequisites
        task.satisfy_me( self.all_outputs )

