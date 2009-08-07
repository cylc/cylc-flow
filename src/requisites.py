""" 
A class that holds a list of 

PREREQUISITES,
  usually of the form "file X ready"

or,

POSTREQUISITES,
  usually of the form "file Y ready" 
  
Each requisite is in a state of "satisfied" or "not satisfied".  

All prerequisites must be matched by someone else's postrequisites.
"""

import sys
import re
import logging

class requisites:

    def __init__( self, name, ref_time ):

        # name and id of my "host task" 
        self.task_name = name
        self.task_id = name + '%' + ref_time

        # dict of requisites to populate using self.add()
        self.satisfied = {}

    def add( self, req ):
        # add a requisite
        if req not in self.satisfied:
            self.satisfied[req] = False
        else:
            print "WARNING: attempted to add a duplicate requisite, ' + self.task_id

    def count( self ):
        return len( self.satisfied.keys() )

    def dump( self ):
        for key in self.satisfied.keys():
            print key + " ... ", self.satisfied[ key ]

    def update( self, reqs ):            
        for req in reqs.get_list():
            self.satisfied[ req ] = reqs.is_satisfied( req )

    def downdate( self, reqs ):
        for req in reqs.get_list():
            del self.satisfied[req]

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
        self.satisfied[ req ] = True

    def requisite_exists( self, req ):
        if req in self.satisfied.keys():
            return True
        else:
            return False

    def set_all_satisfied( self ):
        for req in self.satisfied.keys():
            self.satisfied[ req ] = True

    def get_list( self ):
        return self.satisfied.keys()

    def get_requisites( self ):
        return self.satisfied

    def satisfy_me( self, postreqs ):
        log = logging.getLogger( "main." + self.task_name ) 
        # can another's completed postreqs satisfy any of my prequisites?
        for prereq in self.satisfied.keys():
            # for each of my prerequisites
            if not self.satisfied[ prereq ]:
                # if my prerequisite is not already satisfied
                for postreq in postreqs.satisfied.keys():
                    # compare it with each of the other's postreqs
                    if postreq == prereq and postreqs.satisfied[postreq]:
                        # if they match, my prereq has been satisfied
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

    def __init__( self, name, ref_time ):
        self.timed_reqs = {}
        requisites.__init__( self, name, ref_time )

    def add( self, time, req ):
        self.timed_reqs[ time ] = req
        requisites.add( self, req )

    def get_timed_requisites( self ):
        return self.timed_reqs


class fuzzy_requisites( requisites ):

    # for reference-time based prerequisites of the form 
    # "more recent than or equal to this reference time"

    # same as requites except that a delimited cutoff is expected in the
    # string

    def sharpen_up( self, fuzzy, sharp ):
        # replace a fuzzy prerequisite with the actual postrequisite
        # that satisfied it, and set it satisfied. This allows the task
        # run() method to know the actual postrequisite.
        del self.satisfied[ fuzzy ]
        self.satisfied[ sharp ] = True

    def satisfy_me( self, postreqs ):
        log = logging.getLogger( "main." + self.task_name ) 
        # can another's completed postreqs satisfy any of my prequisites?
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
                for postreq in postreqs.satisfied.keys():

                    if postreqs.satisfied[postreq]:
                        # extract reference time from other's postrequisite

                        m = re.compile( "^(.*)(\d{10})(.*)$").match( postreq )
                        if not m:
                            # this postreq can't possibly satisfy a
                            # fuzzy; move on to the next one.
                            continue
                
                        [ other_start, other_reftime, other_end ] = m.groups()

                        if other_start == my_start and other_end == my_end and other_reftime >= my_min and other_reftime <= my_max:
                            possible_satisfiers[ other_reftime ] = postreq
                            found_at_least_one = True
                        else:
                            continue

                if found_at_least_one: 
                    # choose the most recent possible satisfier
                    possible_reftimes = possible_satisfiers.keys()
                    possible_reftimes.sort( key = int, reverse = True )
                    chosen_reftime = possible_reftimes[0]
                    chosen_postreq = possible_satisfiers[ chosen_reftime ]

                    #print "FUZZY PREREQ: " + prereq
                    #print "SATISFIED BY: " + chosen_postreq

                    # replace fuzzy prereq with the actual postreq that satisfied it
                    self.sharpen_up( prereq, chosen_postreq )
                    log.debug( postreqs.task_name + " fuzzy-satisfier: " + chosen_postreq )

    def will_satisfy_me( self, postreqs ):
        # will another's postreqs, if/when completed, satisfy any of my
        # prequisites?

        # this is similar to satisfy_me() but we don't need to know the most
        # recent satisfying postrequisite, just if any one can do it.

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

                for postreq in postreqs.satisfied.keys():

                    # extract reference time from other's postrequisite
                    m = re.compile( "^(.*)(\d{10})(.*)$").match( postreq )
                    if not m:
                        # this postreq can't possibly satisfy a
                        # fuzzy; move on to the next one.
                        continue

                    [ other_start, other_reftime, other_end ] = m.groups()

                    if other_start == my_start and other_end == my_end and other_reftime >= my_min and other_reftime <= my_max:
                        self.sharpen_up( prereq, postreq )
