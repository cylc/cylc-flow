#!/usr/bin/python

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep

foo = spinner()

status = Pyro.core.getProxyForURI("PYRONAME://" + "system_status" )

while True:
    os.system( "clear" )
    char = foo.spin()
    print 
    print char + " System Monitor " + char
    print 
    print status.report()[0] 
    print

    for line in status.report()[1:]:
         print line

    sleep(1)
