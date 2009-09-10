#!/usr/bin/python

import sys

# BROKER:
# A collection of output messages with associated owner ids (of the
# originating tasks) representing the outputs of ALL TASKS in the
# system, and initialised from the outputs of all the tasks.
# "Satisfied" => the output has been completed.

class broker:
    # A broker aggregates output messages from many objects.
    # Each task registers its outputs with the system broker, then each
    # task tries to get its prerequisites satisfied by the broker's
    # outputs.

    def __init__( self ):
        self.all_outputs = {}   # all_outputs[ taskid ] = [ taskid's requisites ]

    def register( self, owner_id, outputs ):
        # because task ids are unique, and all tasks register their
        # outputs anew in each dependency negotiation round, register 
        # should only be called once by each task

        if owner_id in self.all_outputs.keys():
            print "ERROR:", owner_id, "has already registered its outputs"
            sys.exit(1)

        self.all_outputs[ owner_id ] = outputs

        # TO DO: CHECK FOR DUPLICATE OUTPUTS NOT OWNED BY THE SAME TASK
        # type (successive tasks of the same type can register identical
        # outputs if they write staggered restart files.


    def reset( self ):
        # throw away all messages
        # NOTE IF RESET IS NOT USED BEFORE EACH DEPENDENCY ROUND, AN
        # UNREGISTER METHOD WILL BE REQUIRED
        self.all_outputs = {}

    def dump( self ):
        # for debugging
        print "BROKER DUMP:"
        for id in self.all_outputs.keys():
            print " " + id
            for output in self.all_outputs[ id ].get_list():
                print " + " + output

    def negotiate( self, prerequisites ):
        for id in self.all_outputs.keys():
            prerequisites.satisfy_me( self.all_outputs[ id ], id )
