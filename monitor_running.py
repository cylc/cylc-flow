#!/usr/bin/python

"""
Display progress of currently running tasks objects.

For color terminal ASCII escape codes, see
http://ascii-table.com/ansi-escape-sequences.php
"""

import os
import sys
import Pyro.core
from time import sleep
from pyro_ns_name import pyro_object_name
from string import ljust, rjust, split, upper, lower
import config
import datetime


class kit:
    def __init__( self, title ):
        self.pos = 1
        title = " " + title + " "
        self.title = title
        self.len = len( title )

    def boof( self ):
        a = '\033[1;34m'
        for i in range( 1, self.len - 1 ):
            if i == self.pos:
                a += self.title[i] + '\033[0m'
            else:
                a += self.title[i]

        if self.pos == self.len:
            self.pos = 1
        else:
            self.pos += 1

        return [a] 

title = kit( "EcoConnect System Monitor" )

while True:

    try: 
    
        god = Pyro.core.getProxyForURI('PYRONAME://' + pyro_object_name( 'god' ))
        god._setTimeout(1)

        if config.dummy_mode:
            remote_clock = Pyro.core.getProxyForURI('PYRONAME://' + pyro_object_name( 'dummy_clock' ) )
            remote_clock._setTimeout(1)

        while True:

            dt = datetime.datetime.now()
            if config.dummy_mode:
                dt = remote_clock.get_datetime()

            max_name_len = 0
            max_total_len = 0
            max_prog_len = 0
            lines = {}
            all_waiting = {}

            states = god.get_state_summary()

            for task_id in states.keys():
                [name, reftime] = split( task_id, "%" )
                [state, complete, total, latest ] = states[ task_id ]

                if len( name ) > max_name_len:
                    max_name_len = len( name )

                if len( total ) > max_total_len:
                    max_total_len = len( total )

                if int( total ) > max_prog_len:
                    max_prog_len = int( total )

            for task_id in states.keys():
                [name, reftime] = split( task_id, "%" )
                [state, complete, total, latest ] = states[ task_id ]

                prog = ""
                for k in range( 1, int(total) + 1):
                    if k <= int(complete):
                        prog += "|"
                    else:
                        prog += "-"

                prog = ljust( prog, max_prog_len + 1 )

                name = ljust( name, max_name_len + 1 )
                frac = rjust( complete + "/" + total, 2 * max_total_len + 1 )

                ctrl_end = "\033[0m"

                if state == "running":
                    foo_start = "\033[1;37;42m"   # bold white on blue
                    bar_start = "\033[0;34m"  # bold blue
                    line = bar_start + "  " + ctrl_end + foo_start + name + ctrl_end + " " + bar_start + " " + frac + " " + prog + " " + latest + ctrl_end

                    if reftime in lines.keys(): 
                        lines[ reftime ].append( line )

                    else:
                        # first appearane of rt
                        lines[ reftime ] = [ line ]

            # sort reference times using int( string )
            reftimes = lines.keys()
            reftimes.sort( key = int )

            blit = title.boof()
            blit.append( "  Current Running Tasks" )
            blit.append( dt )
            for rt in reftimes:
                if len( lines[rt] ) != 0:
                    blit.append( "\033[1;31m" + "__________" + "\033[0m" ) # red
                    blit.append( "\033[1;31m" + rt + "\033[0m" )  # red

                    for line in lines[rt]:
                        blit.append( line )

            os.system( "clear" )
            for line in blit:
                print line

            sleep(0.5)

    except:
        os.system( "clear" )
        for line in title.boof():
            print line
        print "Connection failed ..."

    sleep( 0.5 )
