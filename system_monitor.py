#!/usr/bin/python

"""
Simple system monitor program.

It connects to the controller's "state" object via Pyro,
and displays its contents in a terminal.

See system_status.py for class documentation.

For color terminal ASCII escape codes, see
http://ascii-table.com/ansi-escape-sequences.php
"""

import os
import sys
import Pyro.core

from spinner import spinner
from time import sleep
from string import ljust, rjust, split

foo = spinner()

def func( rt ):
    return int( rt )

def print_heading():
    os.system( "clear" )
    char = foo.spin()

    print 
    print "\033[1;34m " + char + " System Monitor " + char + "\033[0m"
    print

while True:
    # the following "try" ... "except" block allows the system monitor
    # to keep trying if it can't find the pyro nameserver. This means
    # the the monitor doesn't die when the controller is killed and
    # restarted, but on the other hand bugs in the monitor aren't
    # distinguishable from no nameserver found... 
    # ... could be done better I suspect.

    try: 
    
        remote = Pyro.core.getProxyForURI("PYRONAME://" + "state" )

        while True:

            status = remote.get_status()

            max_name_len = 0
            max_state_len = 0
            max_total_len = 0
            lines = {}

            for task_id in status.keys():
                [name, reftime] = split( task_id, "_" )
                [state, complete, total, latest ] = status[ task_id ]

                if len( name ) > max_name_len:
                    max_name_len = len( name )

                if len( total ) > max_total_len:
                    max_total_len = len( total )

                if len( state ) > max_state_len:
                    max_state_len = len( state )

            for task_id in status.keys():

                [name, reftime] = split( task_id, "_" )
                [state, complete, total, latest ] = status[ task_id ]

                prog = ""
                for k in range( 1, int(total) + 1):
                    if k <= int(complete):
                        prog += "|"
                    else:
                        prog += "-"

                prog = ljust( prog, max_total_len +4 )

                name = ljust( name, max_name_len + 1 )
                frac = rjust( complete + "/" + total, 2 * max_total_len + 1 )

                ctrl_end = "\033[0m"

                if state == "running":
                    state = ljust( state, max_state_len + 1 )
                    foo_start = "\033[1;37;44m"   # bold white on blue
                    bar_start = "\033[1;34m"  # bold blue
                    line = bar_start + "  o " + ctrl_end + foo_start + name + ctrl_end + " " + bar_start + state + " " + frac + " " + prog + " " + latest + ctrl_end

                elif state == "waiting":
                    state = ljust( state, max_state_len + 1 )
                    foo_start = "\033[31m"        # red
                    line = foo_start + "  o " + name + "  " + state + " " + frac + " " + prog + " " + latest + ctrl_end

                elif state == "finishd":
                    state = ljust( state, max_state_len + 1 )
                    foo_start = "\033[0m"         # black
                    line = foo_start + "  o " + name + "  " + state + " " + frac + " " + prog + " " + latest + ctrl_end

                else:
                    line = "!ERROR!"

                if reftime in lines.keys(): 
                    lines[ reftime ].append( line )
                else:
                    lines[ reftime ] = [ line ]

            # sort reference times using int( string )
            reftimes = lines.keys()
            reftimes.sort( key = int )

            print_heading()

            for rt in reftimes:
                print "\033[1;31m" + "__________" + "\033[0m"  # red
                print "\033[1;31m" + rt + "\033[0m"  # red
                #print ""

                #lines[rt].sort()
                for line in lines[rt]:
                    print line

                print ""

            sleep(1)

    except:
        print_heading()
        print "Connection to nameserver failed ..."

    sleep(1)  
