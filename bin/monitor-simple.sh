#!/usr/bin/python

"""
Display the state of all existing tasks.

NOTE: ONLY DETECTS DUMMY MODE VS REAL TIME MODE AT STARTUP
(so restart this if you restart sequenz in different mode)

For color terminal ASCII escape codes, see
http://ascii-table.com/ansi-escape-sequences.php
"""

import os
import sys
import Pyro.core
from time import sleep
import pyro_ns_naming
from string import split
import datetime
from reference_time import _rt_to_dt

import config

class kit:
    def __init__( self, title ):
        self.pos = 1
        title = " " + title + " "
        self.title = title
        self.len = len( title )

    def boof( self ):
        a =  '\033[1;31m'
        for i in range( 1, self.len - 1):
            if i == self.pos:
                a += self.title[i] + '\033[0m'
            else:
                a += self.title[i]

        if self.pos == self.len:
            self.pos = 1
        else:
            self.pos += 1

        return [a] 

title = kit( "Sequenz System Monitor" )

config = config.config()
config.load()

print
print "here we go ..."
sleep(2)

while True:

    try: 
    
        god = Pyro.core.getProxyForURI('PYRONAME://'+ pyro_ns_naming.name('god', config.get('pyro_ns_group')))
        god._setTimeout(1)


        mode = 'REAL TIME OPERATION'
        if config.get('dummy_mode'):
            mode = 'ACCELERATED CLOCK DUMMY MODE' 
            remote_clock = Pyro.core.getProxyForURI('PYRONAME://'+ pyro_ns_naming.name('dummy_clock', config.get('pyro_ns_group')))
            remote_clock._setTimeout(1)

        while True:

            if config.get('dummy_mode'):
                dt = remote_clock.get_datetime()
            else:
                dt = datetime.datetime.now()

            lines = {}
            states = god.get_state_summary()

            for task_id in states.keys():
                [ name, reftime ] = task_id.split('%')
                [ state, complete, total, latest ] = states[ task_id ]
                
                frac = "(" + str(complete) + "/" + str(total) + ")"

                ctrl_end = "\033[0m"

                if state == "running":
                    foo = "\033[1;37;42m" + name + frac + ctrl_end  # bold white on green

                elif state == "waiting":
                    foo = "\033[35m" + name + ctrl_end       # magenta

                else:
                    foo = name

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

            blit = title.boof()
            blit.append("system name: '" + config.get('system_name') + "'")
            blit.append( mode )
            blit.append( "\033[0;35mwaiting\033[0m \033[1;37;42mrunning\033[0m done" )
            blit.append( '\033[1;34m' + str(dt) + '\033[0m' )
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
        # uncomment for debugging:
        # raise
        os.system( "clear" )
        print "connection failed ..."
        sleep( 1 )
