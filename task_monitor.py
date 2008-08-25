#!/usr/bin/python

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep

foo = spinner()

indent = "     "
indent2 = "        "

def heading():
    os.system( "clear" )
    char = foo.spin()
    print 
    print indent + char + " Task Monitor " + char
    print

while True:
    try:
        state = Pyro.core.getProxyForURI("PYRONAME://" + "state" )

        while True:
            heading()
            print indent2 + state.report()[0] 
            print

            for line in state.report()[1:]:
                print indent2 + line

            sleep(0.5)

    except:
        heading()
        print indent + "(no connection)"

    sleep(0.5)  
