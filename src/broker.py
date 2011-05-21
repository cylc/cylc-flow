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


import sys

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
        self.all_outputs = {}   # all_outputs[ taskid ] = [ taskid's requisites ]

    def register( self, task ):
        # because task ids are unique, and all tasks register their
        # outputs anew in each dependency negotiation round, register 
        # should only be called once by each task

        owner_id = task.id
        outputs = task.outputs

        if owner_id in self.all_outputs.keys():
            print "ERROR:", owner_id, "has already registered its outputs"
            sys.exit(1)

        self.all_outputs[ owner_id ] = outputs

        # TO DO: SHOULD WE CHECK FOR SYSTEM-WIDE DUPLICATE OUTPUTS?
        # (note that successive tasks of the same type can register
        # identical outputs if they write staggered restart files).

    def reset( self ):
        # throw away all messages
        self.all_outputs = {}

    def dump( self ):
        # for debugging
        print "BROKER DUMP:"
        for id in self.all_outputs.keys():
            print " " + id
            for output in self.all_outputs[ id ].get_list():
                print " + " + output
               
    def negotiate( self, task ):
        # can my outputs satisfy any of task's prerequisites
        for id in self.all_outputs.keys():
            # TO DO: if task becomes fully satsified mid-loop we could
            # bail out with the following commented-out conditional, but
            # is the cost of doing the test every time more than that of
            # continuing when task is fully satisfied?
            # CONDITIONAL: if task.not_fully_satisfied():
            task.satisfy_me( self.all_outputs[ id ] )

