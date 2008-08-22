#!/usr/bin/python

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep

foo = spinner()

state = Pyro.core.getProxyForURI("PYRONAME://" + "state" )

while True:
    os.system( "clear" )
    char = foo.spin()
    indent = "     "
    indent2 = "        "
    print 
    print indent + char + " Task Monitor " + char
    print 
    print indent2 + state.report()[0] 
    print

    for line in state.report()[1:]:
         print indent2 + line

    sleep(1)
