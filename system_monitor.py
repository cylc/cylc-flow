#!/usr/bin/python

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep
from string import ljust

foo = spinner()

indent = "     "

def sorted_keys( d, func = None ):
    keys = d.keys()
    keys.sort( func )
    return keys

def heading():
    os.system( "clear" )
    char = foo.spin()
    print 
    print indent + char + " System Monitor " + char
    print

while True:
    try:
        state = Pyro.core.getProxyForURI("PYRONAME://" + "state" )

        while True:
            heading()

            status = state.get_status()
            for task in sorted_keys( status ):
                print ljust( task, 15) + " " + status[ task ]

            sleep(1)

    except:
        heading()
        print "Connection to nameserver failed ..."

    sleep(1)  
