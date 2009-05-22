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
import datetime
import Pyro.core
import Pyro.naming
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


def usage():
    print "USAGE: " + sys.argv[0] + " [sequenz system name]"
    print
    print "Monitor the given system, or"
    print "print a list of registered systems and exit."

if len( sys.argv ) == 2:
    # user supplied name of system to monitor
    system_name = sys.argv[1]

elif len( sys.argv ) == 1:
    # no system name supplied
    # lets see what names are registered with Pyro
    system_name = None

else:
    # too many args
    usage()
    sys.exit(1)

# what groups are currently registered with the Pyro nameserver
locator = Pyro.naming.NameServerLocator()
ns = locator.getNS()
ns_groups = {}
n_groups = 0
# loop through registered objects
for obj in ns.flatlist():
    # Extract the group name for each object (GROUP.name).
    # Note that GROUP may contain '.' characters too.
    # E.g. ':Default.ecoconnect.name'
    group = obj[0].rsplit('.', 1)[0]
    # now strip off ':Default'
    # TO DO: use 'sequenz' group!
    group = re.sub( '^:Default\.', '', group )
    if re.match( ':Pyro', group ):
        # avoid Pyro.nameserver itself
        continue

    if group not in ns_groups.keys():
        ns_groups[ group ] = 1
    else:
        ns_groups[ group ] = ns_groups[ group ] + 1

    n_groups = len( ns_groups.keys() )

print "There are ", n_groups, " systems registered with Pyro"
for group in ns_groups.keys():
    print ' + ', group, ' ... ', ns_groups[group], ' objects registered'

if system_name == None:
    print "ABORTING: no system specified to monitor or wait on."
    sys.exit(0)

elif system_name not in ns_groups.keys():
    print "WARNING: waiting for " + system_name + " to be registered." 

else:
    print "Monitoring system " + system_name
        
title = kit( "Sequenz System Monitor" )

print
print "here we go ..."
sleep(2)

while True:

    try: 
        god = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.state_summary')
        print "HELLO"
        god._setTimeout(10)

        try:
            remote_clock = Pyro.core.getProxyForURI('PYRONAME://' + system_name + '.dummy_clock' )
        except:
            mode = 'REAL TIME OPERATION'
            dummy_mode = False
        else:
            dummy_mode = True
            mode = 'ACCELERATED CLOCK DUMMY MODE' 
            remote_clock._setTimeout(1)

        while True:

            if dummy_mode:
                dt = remote_clock.get_datetime()
            else:
                dt = datetime.datetime.now()

            lines = {}
            states = god.get_summary()

            for task_id in states.keys():
                [ name, reftime ] = task_id.split('%')
                [ state, complete, total, latest ] = states[ task_id ]
                
                frac = "(" + str(complete) + "/" + str(total) + ")"

                ctrl_end = "\033[0m"

                if state == "running":
                    foo = "\033[1;37;42m" + name + frac + ctrl_end  # bold white on green

                elif state == "waiting":
                    foo = "\033[35m" + name + ctrl_end       # magenta

                elif state == "failed":
                    foo = "\033[1;37;41m" + name + ctrl_end       # bold white on red

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
            blit.append("system name: topnet-test")
            blit.append( mode )
            blit.append( "\033[0;35mwaiting\033[0m \033[1;37;42mrunning\033[0m done \033[1;37;41mfailed\033[0m" )
            blit.append( '\033[1;34m' + str(dt) + '\033[0m' )
            blit.append("")
            for rt in reftimes:
                foo = '\033[1;34m'
                blit.append( foo + lines[rt] )

            os.system( "clear" )
            for line in blit:
                print line
            sleep(0.5)

    except:
        raise
        #os.system( "clear" )
        print "connection failed ..."
        sleep( 1 )
