#!/usr/bin/python

"""
Very simple system monitor program.

It connects to the controller's "state" object via Pyro,
and displays its contents in a terminal.

See system_status.py for class documentation.

For color terminal ASCII escape codes, see
http://ascii-table.com/ansi-escape-sequences.php
"""

import os
import sys
import Pyro.core

from time import sleep
from string import split

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

title = kit( "EcoConnect System Monitor" )

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

            lines = {}

            for task_id in status.keys():

                [name, reftime] = split( task_id, "_" )
                [state, complete, total, latest ] = status[ task_id ]

                frac = "(" + complete + "/" + total + ")"

                ctrl_end = "\033[0m"

                if state == "running":
                    foo = "\033[1;37;42m" + name + frac + ctrl_end  # bold white on green

                elif state == "waiting":
                    foo = "\033[35m" + name + ctrl_end       # magenta

                else:
                    foo = name

                hour = int( reftime[8:10] )

                if hour == 6 or hour == 18:
                    indent = ""
                elif hour == 0 or hour == 12:
                    indent = ' |--'
                else:
                    indent = ' |----'

                if reftime in lines.keys():
                    lines[reftime] += ' ' + foo
                else:
                    lines[reftime] = indent + "\033[1;34m" + reftime + "\033[0m " + foo
                
            # sort reference times using int( string )
            reftimes = lines.keys()
            reftimes.sort( key = int )

            blit = title.boof()
            blit.append("  Current Task Objects")
            blit.append("  \033[0;35mwaiting\033[0m \033[1;37;42mrunning\033[0m done" )
            blit.append("")
            for rt in reftimes:
                blit.append( lines[rt] )

            os.system( "clear" )
            for line in blit:
                print line
            sleep(0.5)

    except:
        os.system( "clear" )
        for line in title.boof():
            print line
        print "Connection to nameserver failed ..."

    sleep( 0.5 )
