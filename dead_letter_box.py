#!/usr/bin/python

"""
class to take incoming pyro messages that are not directed at a specific task object 
(the sender can direct warning messages here if the desired task object no longer
exists, for example)
"""

import Pyro.core

class dead_letter_box( Pyro.core.ObjBase ):

    def __init__( self ):
        print "Initialising Dead Letter Box"
        Pyro.core.ObjBase.__init__(self)

    def incoming( self, message ):
        print
        print "WARNING: Dead Letter: " + message
        print
