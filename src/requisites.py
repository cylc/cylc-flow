#!/usr/bin/python

import re
import sys
import logging

# requisites have to 'get' the main log anew each time logging is
# required, because thread locking in the logging module is incompatible
# with 'deep copying' of requisites elsewhere in the code.

class requisites:

    # A collection of text messages  each of which are either
    # "satisfied" or "not satisfied", and methods to work with them.  

    def __init__( self, name, ref_time ):

        # name and id of my "host task" 
        self.task_name = name
        self.task_id = name + '%' + ref_time

        # dict of requisites to populate using self.add()
        self.satisfied = {}

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

    def add( self, message ):
        # Add a new prerequisite message in an UNSATISFIED state.
        # We don't need to check if the new prerequisite message has
        # already been registered because duplicate prerequisites add no
        # information.
        self.satisfied[message] = False

    def satisfy_me( self, outputs ):
        log = logging.getLogger( "main." + self.task_name ) 

        # can another's completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for output in outputs.satisfied.keys():
                    # compare it with each of the other's outputs
                    if output == prereq and outputs.satisfied[output]:
                        # if they match, my prereq has been satisfied
                        log.debug( outputs.task_name + " satisfied: " + prereq )
                        self.set_satisfied( prereq )

    def will_satisfy_me( self, outputs ):
        # will another's outputs, when completed, satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            #print "PRE: " + prereq
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for output in outputs.satisfied.keys():
                    #print "POST: " + output
                    # compare it with each of the other's outputs
                    if output == prereq:   # (DIFFERENT FROM ABOVE HERE)
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )


class outputs( requisites ):

    # outputs are requisites for which each message represents an
    # output or milestone (e.g. 'file X ready' or 'task Y completed') 
    # that has either been completed (satisfied) or not (not satisfied).

    # additionally, outputs have an estimated completion time associated
    # with each message, which is used to simulate task execution in
    # dummy mode.

    def __init__( self, name, ref_time ):
        self.timed_reqs = {}
        requisites.__init__( self, name, ref_time )

    def add( self, t, message ):
        # Add a new output message, with estimated completion time t, in
        # an UNSATISFIED state.

        if message in self.satisfied.keys():
            # Identical outputs should not be generated at different
            # times; this would cause problems for anything that depends
            # on them. 

            log = logging.getLogger( "main." + self.task_name ) 
            log.critical( 'output already registered: ' + message )
            sys.exit(1)

        if t in self.timed_reqs.keys():
            # The system cannot currently handle multiple outputs
            # generated at the same time; only the last will be
            # registered, the others get overwritten. 

            log = logging.getLogger( "main." + self.task_name ) 
            log.critical( 'multiple ' + self.task_name + ' outputs registered for ' + str(t) + ' minutes' )
            log.critical( '(this may mean the last output is at the task finish time)' )
            sys.exit(1)



        self.satisfied[message] = False
        self.timed_reqs[ t ] = message

    def get_timed_requisites( self ):
        return self.timed_reqs


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

    def satisfy_me( self, outputs ):
        log = logging.getLogger( "main." + self.task_name ) 


        # can another's completed outputs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if it is not yet satisfied

                # extract fuzzy reference time bounds from my prerequisite
                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
                if not m:
                    log.critical( "FAILED TO MATCH MIN:MAX IN " + prereq )
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
                    log.debug( outputs.task_name + " fuzzy-satisfier: " + chosen_output )

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
                    log.critical( "FAILED TO MATCH MIN:MAX IN " + prereq )
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


class broker ( requisites ):

    # A broker aggregates output messages from many objects.

    # Each task registers its outputs with the system broker, then each
    # task tries to get its prerequisites satisfied by the broker's
    # outputs.

    # Depends on requisites rather than outputs because we don't need
    # the output time information here.

    def __init__( self ):
        requisites.__init__( self, 'broker', '2999010101' )


    def register( self, outputs ):
        # add a new batch of output messages
        for output in outputs.get_list():
            if output in self.satisfied.keys():
                # across the whole system, prerequisites need not be
                # unique (many tasks can depend on the same upstream
                # output) but outputs should be unique (if two tasks are
                # claiming to have generated the same file, for
                # instance, this would almost certainly indicate a
                # system configuration error). 
                log = logging.getLogger( "main." + self.task_name ) 
                log.critical( 'duplicate output detected: ' + output )
                sys.exit(1)

            self.satisfied[ output ] = outputs.is_satisfied( output )


    def reset( self ):
        # throw away all messages
        self.satisfied = {}


    #def unregister( self, outputs ):
    # THIS METHOD WAS USED TO UNREGISTER THE OUTPUT MESSAGES OF A
    # SPENT TASK BEFORE DELETING IT, BUT IT IS NOT NEEDED IF WE
    # CALL BROKER.RESET() BEFORE EACH DEPENDENCY NEGOTIATION CYCLE
    #    for output in outputs.get_list():
    #        del self.satisfied[output]


