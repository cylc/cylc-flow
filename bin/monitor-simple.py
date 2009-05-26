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
import config
import datetime
import Pyro.core
from time import sleep
from string import split
from reference_time import _rt_to_dt

config = config.config()
config.load()

print
print "here we go ..."
sleep(2)

while True:

    try: 
    
        god = Pyro.core.getProxyForURI('PYRONAME://'+ config.get('pyro_ns_group') + '.' + 'state_summary')
        god._setTimeout(10)

        mode = 'real time'
        if config.get('dummy_mode'):
            mode = 'dummy time' 
            remote_clock = Pyro.core.getProxyForURI('PYRONAME://'+ config.get('pyro_ns_group') + '.' + 'dummy_clock' )
            remote_clock._setTimeout(10)

        system_name = config.get('system_name')

        while True:
            if config.get('dummy_mode'):
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

                # indentify not-abdicated-yet indicator in task name
                not_abdicated = False
                m = re.match( '(\*)(.*)', name )
                if m:
                    not_abdicated = True
                    [ junk, name ] = m.groups()

                frac = "(" + str(complete) + "/" + str(total) + ")"

                if state == "running":
                    foo = "\033[1;37;42m" + name + frac + ctrl_end  # bold white on green

                elif state == "waiting":
                    foo = "\033[35m" + name + ctrl_end       # magenta

                elif state == "failed":
                    foo = "\033[1;37;41m" + name + ctrl_end       # bold white on red

                else:
                    foo = name

                if not_abdicated:
                    foo = "\033[1;37;45m" + '*' + ctrl_end + foo

                hour = int( reftime[8:10] )

                indent = ' - '
                if hour == 6 or hour == 18 or hour == 0 or hour == 12:
                    indent = ""

                if reftime in lines.keys():
                    lines[reftime] += ' ' + foo
                else:
                    lines[reftime] = indent + reftime + "\033[0m " + foo
                
            # sort reference times using int( string )
            reftimes = lines.keys()
            reftimes.sort( key = int )

            blit = [ "\033[1;37;46m" + system_name + ctrl_end + ' ' + mode ]
            blit.append( '\033[1;37;34m ' + dt.strftime( "%Y/%m/%d %H:%M:%S" ) + '\033[0m' )
            blit.append( "\033[0;35mwaiting\033[0m \033[1;37;42mrunning\033[0m done \033[1;37;41mfailed\033[0m")
            blit.append( '\033[1;37;45m' + '*' + '\033[0m' + ' => task not yet abdicated' )
            blit.append( '============================' )
            blit.append("")
            for rt in reftimes:
                # colour reference time relative to clock time
                rtdt = _rt_to_dt( rt )
                if dt > rtdt:
                    foo = '\033[1;35m'
                else:
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
