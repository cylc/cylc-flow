#!/usr/bin/python

# a broker object acts as a middleman to allow us to optionally
# avoid the O(n^2) task interaction loop. Each task registers
# its postrequisites with the broker, then each task tries to
# get its prerequisites satisfied by the broker.

from requisites import requisites

class broker:

    def __init__( self ):
        self.requisites = requisites( 'broker', [] )

    def register( self, task_requisites ):
        # task updates me with its completed postrequisites
        self.requisites.update( task_requisites )
        #print "register: ", self.requisites.count()

    def unregister( self, task_requisites ):
        # delete requisites from a dying task
        self.requisites.downdate( task_requisites )
        #print "unregister: ", self.requisites.count()

    def get_requisites( self ):
        return self.requisites
