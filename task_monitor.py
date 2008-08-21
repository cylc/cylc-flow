#!/usr/bin/python

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep

foo = spinner()

status = Pyro.core.getProxyForURI("PYRONAME://" + "status" )

while True:
    os.system( "clear" )
    char = foo.spin()
    indent = "     "
    indent2 = "        "
    print 
    print indent + char + " Task Monitor " + char
    print 
    print indent2 + status.report()[0] 
    print

    for line in status.report()[1:]:
         print indent2 + line

    sleep(1)
