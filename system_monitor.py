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
    print "current task objects"
    print

while True:
    # uncomment the following "try" and "except" code to allow the
    # system monitor to keep trying if it can't find the pyro
    # nameserver. This means the the monitor doesn't die when the
    # controller is killed and restarted, but on the other hand bugs in
    # the monitor aren't distinguishable from no nameserver found...
    # could be done better, no doubt.

    #try: 
    
        reftimes_old = []
        len_refimes_old = {}
        n_blank_lines = 0

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

                ctrl_start = ctrl_end = ctrl_foo_start = ctrl_bar_start = "\033[0m"
                if state == "running":
                    ctrl_start = "\033[1;37;44m"   # bold white on blue
                    ctrl_foo_start = "\033[1;34m"  # bold blue
                    ctrl_bar_start = "\033[0;34m"  # blue
                elif state == "waiting":
                    ctrl_start = "\033[31m"        # red
                    ctrl_bar_start = "\033[31m"    # red
                elif state == "finished":
                    ctrl_start = "\033[0m"         # black

                state = ljust( state, max_state_len + 1 )
                name = ljust( name, max_name_len + 1 )
                frac = rjust( complete + "/" + total, 2 * max_total_len + 1 )
                line = ctrl_start + " " + name + state + ctrl_end + " " + ctrl_foo_start + frac + " " + prog + ctrl_end + " " + ctrl_bar_start + latest + ctrl_end

                if reftime in lines.keys(): 
                    lines[ reftime ].append( line )
                else:
                    lines[ reftime ] = [ line ]

            # sort reference times using int( string )
            reftimes = lines.keys()
            reftimes.sort( key = int )

            # If a reference time block has disappeared, insert a
            # decreasing number of blank lines in its place so that the
            # monitor display smoothly transitions to the next state.
            # Otherwise the sudden move to the top of the screen makes
            # it hard to keep track of which block is which.  The
            # following code assumes (a) all tasks for a given reference
            # time are deleted at once, and (b) the earliest reference
            # time always gets deleted first.

            n_lost_lines = 0
            for rt in reftimes_old:
                if rt not in reftimes:
                    n_lost_lines += ( len_reftimes_old[rt] + 4 )

            reftimes_old = reftimes
            len_reftimes_old = {}
            for rt in reftimes:
                len_reftimes_old[rt] = len( lines[rt] )

            if n_lost_lines > 0:
                n_blank_lines = n_lost_lines

            print_heading()

            if n_blank_lines > 0:
                for k in range( 1, n_blank_lines ):
                    print ""
                n_blank_lines -= 1

            # blank lines calc finished

            for rt in reftimes:
                print "  \033[1;35m** " + rt + " **\033[0m"  # magenta
                print ""

                lines[rt].sort()
                for line in lines[rt]:
                    print line

                print ""

            sleep(1)

    #except:
    #    print_heading()
    #    print "Connection to nameserver failed ..."

    #sleep(1)  
