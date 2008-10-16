""" 
A class that holds a list of 

PREREQUISITES,
  usually of the form "input file X required", or

POSTREQUISITES,
  usually of the form "output file Y completed" 
  
Each requisite is in a state of "satisfied" or "not satisfied".  

All prerequisites must be matched by someone else's postrequisites, but
there may be extra postrequisites, to be used for monitoring progress.
"""

import sys
import re
import logging

class requisites:

    def __init__( self, task_name, reqs ):

        # name of my "host task" 
        # (is there a better way to get this information?)
        self.task_name = task_name
        # should use task identity instead of name so that the satifying
        # ref time is also identified for fuzzy prerequisites?

        self.satisfied = {}
        self.ordered_list = []
        for req in reqs:
            self.satisfied[req] = False
            self.ordered_list.append( req ) 

    def all_satisfied( self ):
        if False in self.satisfied.values(): 
            return False
        else:
            return True

    def is_satisfied( self, req ):
        if self.satisfied[ req ]:
            return True
        else:
            return False

    def set_satisfied( self, req ):
        if req in self.ordered_list:
            self.satisfied[ req ] = True
        else:
            print "ERROR: unknown requisite: " + req
            sys.exit(1)

    def requisite_exists( self, req ):
        if req in self.ordered_list:
            return True
        else:
            return False

    def set_all_satisfied( self ):
        for req in self.ordered_list:
            self.satisfied[ req ] = True

    def get_list( self ):
        return self.ordered_list

    def get_requisites( self ):
        return self.satisfied

    def satisfy_me( self, postreqs ):
        # can another's completed postreqs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for postreq in postreqs.satisfied.keys():
                    # compare it with each of the other's postreqs
                    if postreq == prereq and postreqs.satisfied[postreq]:
                        # if they match, my prereq has been satisfied
            
                        log = logging.getLogger( "main." + self.task_name ) 
                        log.debug( postreqs.task_name + " satisfied: " + prereq )

                        self.set_satisfied( prereq )

    def will_satisfy_me( self, postreqs ):
        # will another's postreqs, when completed, satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            #print "PRE: " + prereq
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for postreq in postreqs.satisfied.keys():
                    #print "POST: " + postreq
                    # compare it with each of the other's postreqs
                    if postreq == prereq:   # (DIFFERENT FROM ABOVE HERE)
                        # if they match, my prereq has been satisfied
                        self.set_satisfied( prereq )


class timed_requisites( requisites ):
    # use for postrequisites with estimated completion times

    def __init__( self, task_name, timed_reqs ):

        reqs = []
        self.completion_time = {}
        for entry in timed_reqs:
            [ time, req ] = entry
            reqs.append( req )

            self.completion_time[ req ] = time 

        requisites.__init__( self, task_name, reqs )

    def get_times( self ):
        return self.completion_time


class fuzzy_requisites( requisites ):

    # for reference-time based prerequisites of the form 
    # "more recent than or equal to this reference time"

    def __init__( self, task_name, reqs ):
        requisites.__init__( self, task_name, reqs ) 

    def sharpen_up( self, fuzzy, sharp ):
        # replace the fuzzy prerequisite with the actual postrequisite
        # that satisfied it, so the task run() method can use it.
        i = self.ordered_list.index( fuzzy )
        self.ordered_list.remove( fuzzy )
        self.ordered_list.insert( i, sharp ) 
        
        del self.satisfied[ fuzzy ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, postreqs ):
        # can another's completed postreqs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied

                # extract reference time from my prerequisite
                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
                if not m:
                    print "FAILED TO MATCH MIN:MAX IN " + prereq
                    sys.exit(1)

                [ my_start, my_minmax, my_end ] = m.groups()
                [ my_min, my_max ] = my_minmax.split(':')

                for postreq in postreqs.satisfied.keys():

                    if postreqs.satisfied[postreq]:
                        # extract reference time from other's postrequisite
                        m = re.compile( "^(.*)(\d{10})(.*)$").match( postreq )
                        if not m:
                            print "FAILED TO MATCH REFTIME IN " + postreq
                            sys.exit(1)
                
                        [ other_start, other_reftime, other_end ] = m.groups()

                        if other_start == my_start and other_end == my_end:
                            if other_reftime >= my_min and other_reftime <= my_max:
                                #print "FUZZY PREREQ: " + prereq
                                #print "SATISFIED BY: " + postreq
            
                                log = logging.getLogger( "main." + self.task_name ) 
                                # now replace the fuzzy prereq with the
                                # actual postreq that satisfied it
                                self.sharpen_up( prereq, postreq )

                                log.debug( postreqs.task_name + " fuzzy-satisfier: " + postreq )

    def will_satisfy_me( self, postreqs ):
        # will another's postreqs, when completed, satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied

                # extract reference time from my prerequisite
                m = re.compile( "^(.*)(\d{10}:\d{10})(.*)$").match( prereq )
                if not m:
                    print "FAILED TO MATCH MIN:MAX IN " + prereq
                    sys.exit(1)

                [ my_start, my_minmax, my_end ] = m.groups()
                [ my_min, my_max ] = my_minmax.split(':')

                for postreq in postreqs.satisfied.keys():

                    # extract reference time from other's postrequisite
                    m = re.compile( "^(.*)(\d{10})(.*)$").match( postreq )
                    if not m:
                        print "FAILED TO MATCH REF TIME IN " + postreq
                        sys.exit(1)

                    [ other_start, other_reftime, other_end ] = m.groups()

                    if other_start == my_start and other_end == my_end:
                        if other_reftime >= my_min and other_reftime <= my_max:
                            self.sharpen_up( prereq, postreq )
