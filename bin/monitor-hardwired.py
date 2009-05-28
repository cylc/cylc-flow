#!/usr/bin/python

"""
Display the state of all existing tasks.

NOTE: ONLY DETECTS DUMMY MODE VS REAL TIME MODE AT STARTUP
(so restart this if you restart sequenz in different mode)

For color terminal ASCII escape codes, see
http://ascii-table.com/ansi-escape-sequences.php
"""

import os
import re
import sys
import pyrex
import datetime
import Pyro.core
import Pyro.naming
from time import sleep
from string import split

def usage():
    print "USAGE: " + sys.argv[0] + " <system-name>"
    print "Monitor the specified sequenz system"

ns_groups = pyrex.discover()

if len( sys.argv ) == 2:
    # user supplied name of system to monitor
    system_name = sys.argv[1]
else:
    usage()
    ns_groups.print_info()
    sys.exit(1)

if ns_groups.registered( system_name ):
    print "Monitoring system " + system_name
else:
    print "WARNING: " + system_name + " not yet registered:" 
    ns_groups.print_info()
    print "waiting ..."

print
print "here we go ..."
sleep(2)

while True:

    try: 
        god = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.state_summary')
        god._setTimeout(10)

        dummy_mode = god.get_dummy_mode()

        if dummy_mode:
            remote_clock = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.dummy_clock' )
            remote_clock._setTimeout(10)
            mode = 'dummy mode' 
        else:
            mode = 'real time'

        while True:

            if dummy_mode:
                dt = remote_clock.get_datetime()
            else:
                dt = datetime.datetime.now()

            lines = {}
            states = god.get_summary()

            task_ids = states.keys()
            task_ids.sort()

            for task_id in task_ids:
                [ name, reftime ] = task_id.split('%')
                [ state, complete, total, latest ] = states[ task_id ]

                ctrl_end = "\033[0m"

                # identify not-abdicated-yet indicator in task name
                not_abdicated = False
                m = re.match( '(\*)(.*)', name )
                if m:
                    not_abdicated = True
                    [ junk, name ] = m.groups()

                frac = "(" + str(complete) + "/" + str(total) + ")"

                if state == "running":
                    foo = "\033[1;37;42m" + name + frac + ctrl_end  # bold white on green

                elif state == "waiting":
                    foo = "\033[35m" + name + ctrl_end              # magenta

                elif state == "failed":
                    foo = "\033[1;37;41m" + name + ctrl_end         # bold white on red

                else:
                    foo = name

                if not_abdicated:
                    foo = "\033[1;37;43m" + '*' + ctrl_end + foo

                hour = int( reftime[8:10] )

                if reftime in lines.keys():
                    lines[reftime] += ' ' + foo
                else:
                    lines[reftime] = reftime + "\033[0m " + foo
                
            # sort reference times using int( string )
            reftimes = lines.keys()
            reftimes.sort( key = int )

            blit = [ "\033[1;37;46m" + system_name + ctrl_end + ' ' + mode ]
            blit.append( '\033[1;37;34m ' + dt.strftime( "%Y/%m/%d %H:%M:%S" ) + '\033[0m' )
            blit.append( "\033[0;35mwaiting\033[0m \033[1;37;42mrunning\033[0m done \033[1;37;41mfailed\033[0m")
            blit.append( '\033[1;37;43m' + '*' + '\033[0m' + ' => task not yet abdicated' )
            blit.append( '============================' )
            blit.append("")
            for rt in reftimes:
                foo = '\033[1;34m'
                blit.append( foo + lines[rt] )

            os.system( "clear" )
            for line in blit:
                print line
            sleep(0.5)

    except:
        #raise
        #os.system( "clear" )
        print "connection failed ..."
        sleep( 1 )
