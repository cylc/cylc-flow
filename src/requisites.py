#!/usr/bin/python

import re
import sys
import logging

# REQUISITES (base class)
# A collection of messages, each "satisfied" or not.

# OUTPUTS:
# A collection of messages with associated times, representing the
# outputs of ONE TASK and their estimated completion times. 
# "Satisfied" => the output has been completed.

# BROKER:
# A collection of output messages with associated owner ids (of the
# originating tasks) representing the outputs of ALL TASKS in the
# system, and initialised from the outputs of all the tasks.
# "Satisfied" => the output has been completed.

# PREREQUISITES:
# A collection of messages representing the prerequisite conditions
# of ONE TASK. "Satisfied" => the prerequisite has been satisfied.
# Prerequisites can interact with a broker (above) to get satisfied.

# NOTE ON LOGGING:
# Requisite classes have to 'get' the log each time logging is required,
# rather than hold a self.log, because thread locking in the logging
# module is incompatible with 'deep copying' of requisites elsewhere in
# the code.

class requisites:
    # A collection of messages, each "satisfied" or not.

    def __init__( self ):
        self.satisfied = {}  # self.satisfied[ "message" ] = True/False

    def count( self ):
        # how many messages are stored
        return len( self.satisfied.keys() )

    def count_satisfied( self ):
        # how many messages are stored
        n = 0
        for message in self.satisfied.keys():
            if self.satisfied[ message ]:
                n += 1
        return n

    def dump( self ):
        # print out each message and its state; use for debugging
        for key in self.satisfied.keys():
            print key + " ... ", self.satisfied[ key ]

    def all_satisfied( self ):
        if False in self.satisfied.values(): 
            return False
        else:
            return True

    def is_satisfied( self, message ):
        if self.satisfied[ message ]:
            return True
        else:
            return False

    def set_satisfied( self, message ):
        self.satisfied[ message ] = True

    def exists( self, message ):
        if message in self.satisfied.keys():
            return True
        else:
            return False

    def set_all_satisfied( self ):
        for message in self.satisfied.keys():
            self.satisfied[ message ] = True

    def get_list( self ):
        return self.satisfied.keys()


class prerequisites( requisites ):

    # prerequisites are requisites for which each message represents a
    # prerequisite condition that is either satisifed or not satisfied.

    # prerequisite messages can change state from unsatisfied to
    # satisfied if another object has a matching output message that is
    # satisfied (i.e. a completed output). 

    def __init__( self, task_name, ref_time ):
        self.task_name = task_name
        self.ref_time = ref_time

        requisites.__init__( self )

    def add( self, message ):
        # Add a new prerequisite message in an UNSATISFIED state.
        # We don't need to check if the new prerequisite message has
        # already been registered because duplicate prerequisites add no
        # information.
        self.satisfied[message] = False

    def satisfy_me( self, outputs, owner_id ):
        log = logging.getLogger( "main." + self.task_name )            
        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for output in outputs.satisfied.keys():
                    # compare it with each of the outputs
                    if output == prereq and outputs.satisfied[output]:
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )
                        log.warning( 'Got "' + output + '" from ' + owner_id + ', for ' + self.ref_time )

    def will_satisfy_me( self, outputs, owner_id ):
        # will the outputs, when completed, satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            #print "PRE: " + prereq
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for output in outputs.satisfied.keys():
                    #print "POST: " + output
                    # compare it with each of the outputs
                    if output == prereq:   # (DIFFERENT FROM ABOVE HERE)
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )


class fuzzy_prerequisites( prerequisites ):

    # for reference-time based prerequisites of the form 
    # "more recent than or equal to this reference time"

    # a delimited time cutoff is expected in the message string

    # requires more complex satisfy_me() and will_satisfy_me() methods.

    def sharpen_up( self, fuzzy, sharp ):
        # replace a fuzzy prerequisite with the actual output message
        # that satisfied it, and set it satisfied. This allows the task
        # run() method to know the actual output message.
        del self.satisfied[ fuzzy ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, outputs, owner_id ):
        log = logging.getLogger( "main." + self.task_name )            
        # can any completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if it is not yet satisfied

                # extract fuzzy reference time bounds from my prerequisite
                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
                if not m:
                    #log.critical( "FAILED TO MATCH MIN:MAX IN " + prereq )
                    sys.exit(1)

                [ my_start, my_minmax, my_end ] = m.groups()
                [ my_min, my_max ] = my_minmax.split(':')

                possible_satisfiers = {}
                found_at_least_one = False
                for output in outputs.satisfied.keys():

                    if outputs.satisfied[output]:
                        # extract reference time from other's output
                        # message

                        m = re.compile( "^(.*)(\d{10})(.*)$").match( output )
                        if not m:
                            # this output can't possibly satisfy a
                            # fuzzy; move on to the next one.
                            continue
                
                        [ other_start, other_reftime, other_end ] = m.groups()

                        if other_start == my_start and other_end == my_end and other_reftime >= my_min and other_reftime <= my_max:
                            possible_satisfiers[ other_reftime ] = output
                            found_at_least_one = True
                        else:
                            continue

                if found_at_least_one: 
                    # choose the most recent possible satisfier
                    possible_reftimes = possible_satisfiers.keys()
                    possible_reftimes.sort( key = int, reverse = True )
                    chosen_reftime = possible_reftimes[0]
                    chosen_output = possible_satisfiers[ chosen_reftime ]

                    #print "FUZZY PREREQ: " + prereq
                    #print "SATISFIED BY: " + chosen_output

                    # replace fuzzy prereq with the actual output that satisfied it
                    self.sharpen_up( prereq, chosen_output )
                    log.warning( 'Got "' + chosen_output + '" from ' + owner_id + ', for ' + self.ref_time )

    def will_satisfy_me( self, outputs ):
        # will another's outputs, if/when completed, satisfy any of my
        # prequisites?

        # this is similar to satisfy_me() but we don't need to know the most
        # recent satisfying output message, just if any one can do it.

        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied

                # extract reference time from my prerequisite
                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
                if not m:
                    #log.critical( "FAILED TO MATCH MIN:MAX IN " + prereq )
                    sys.exit(1)

                [ my_start, my_minmax, my_end ] = m.groups()
                [ my_min, my_max ] = my_minmax.split(':')

                for output in outputs.satisfied.keys():

                    # extract reference time from other's output message
                    m = re.compile( "^(.*)(\d{10})(.*)$").match( output )
                    if not m:
                        # this output can't possibly satisfy a
                        # fuzzy; move on to the next one.
                        continue

                    [ other_start, other_reftime, other_end ] = m.groups()

                    if other_start == my_start and other_end == my_end and other_reftime >= my_min and other_reftime <= my_max:
                        self.sharpen_up( prereq, output )


class outputs( requisites ):

    # outputs are requisites for which each message represents an
    # output or milestone that has either been completed (satisfied) or
    # not (not satisfied).

    # additionally, each output message has an associated estimated
    # completion time, used to simulate task execution in dummy mode.

    def __init__( self, task_name, ref_time ):
        self.task_name = task_name
        self.ref_time = ref_time

        self.message = {}    # self.message[ t ] = "message"
        self.time = {}       # self.time[ "message" ] = t

        requisites.__init__( self )

    def add( self, t, message ):
        # Add a new unsatisfied output message for time t

        log = logging.getLogger( "main." + self.task_name )            

        # prefix task id to special 'started' and 'finished' outputs
        if message == 'started' or message == 'finished':
            message = self.task_name + '%' + self.ref_time + ' ' + message

        if message in self.satisfied.keys():
            # duplicate output messages are an error.
            log.critical( 'already registered: ' + message ) 
            sys.exit(1)

        if t in self.message.keys():
            # The system cannot currently handle multiple outputs
            # generated at the same time; only the last will be
            # registered, the others get overwritten. 

            log.critical( 'two outputs registered for ' + str(t) + ' minutes' )
            log.critical( '(may mean the last output is at the task finish time)' ) 
            log.critical( ' one: "' + self.message[ t ] + '"' )
            log.critical( ' two: "' + message + '"' )
            sys.exit(1)

        self.satisfied[message] = False
        self.message[ t ] = message
        self.time[message] = t

    def get_timed_requisites( self ):
        return self.message


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
