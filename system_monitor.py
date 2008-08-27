#!/usr/bin/python

"""
Simple system monitor program.

It connects to the controller's "state" system_status object via the
Pyro nameserver, and displays the contents therein in a terminal.

See system_status.py for class documentation.
"""

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep
from string import ljust, rjust, split

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
    print indent + "\033[34m" + char + " System Monitor " + char + "\033[0m"
    print

while True:
    try:
        remote = Pyro.core.getProxyForURI("PYRONAME://" + "state" )

        while True:

            status = remote.get_status()

            max_name_len = 0
            max_state_len = 0
            max_total_len = 0
            lines = []

            for task_id in sorted_keys( status ):
                [name, reftime] = split( task_id, "_" )
                [state, complete, total] = status[ task_id ]

                if len( name ) > max_name_len:
                    max_name_len = len( name )

                if len( total ) > max_total_len:
                    max_total_len = len( total )

                if len( state ) > max_state_len:
                    max_state_len = len( state )

            for task_id in sorted_keys( status ):

                [name, reftime] = split( task_id, "_" )
                [state, complete, total] = status[ task_id ]

                prog = ""
                for k in range( 1, int(total) + 1):
                    if k <= int(complete):
                        prog += "|"
                    else:
                        prog += "-"

                prog = ljust( prog, max_total_len +1 )

                ctrl_start = ctrl_end = "\033[0m"
                if state == "running":
                    ctrl_start = "\033[31m"        # red
                elif state == "waiting":
                    ctrl_start = "\033[32m"        # green
                elif state == "finished":
                    ctrl_start = "\033[0m"         # default

                state = ljust( state, max_state_len + 1 )

                name = ljust( name, max_name_len + 1 )

                frac = rjust( complete + "/" + total, 2 * max_total_len + 1 )


                lines.append( ctrl_start + " " + name + "(" + reftime + ") " + state + " " + frac + " " + prog + ctrl_end )

            heading()
            for line in lines:
                print line

            sleep(1)

    except:
        heading()
        print "Connection to nameserver failed ..."

    sleep(1)  
