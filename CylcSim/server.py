#!/usr/bin/env python

import sys
import socket
import Pyro, Pyro.core
import logging
from time import sleep

class report( Pyro.core.ObjBase ):
    def __init__( self, n_tasks ):
        self.n_tasks = n_tasks
        Pyro.core.ObjBase.__init__(self)

    def get_n( self ):
        return n_tasks

class task( Pyro.core.ObjBase ):
    request_count = 0
    def __init__( self, id ):
        self.id = id
        self.messages = []
       # self.log = logging.getLogger('main')
        Pyro.core.ObjBase.__init__(self)

    def incoming( self, msg ):
        #self.log.info( self.id + ' INCOMING: ' + msg )
        print self.id + ' INCOMING: ' + msg
        self.__class__.request_count += 1
        self.messages.append( msg )

    def process( self ):
        #self.log.info( self.id + ' PROCESS: hello' )
        print '   ', self.id + ' PROCESS: hello'

def process( pool ):
    print 'PROCESSING'
    for itask in pool:
        sleep(1)
        itask.process()

if len(sys.argv) != 3:
    print "USAGE: server.py <N> <P>"
    print "ARGS:"
    print "   N  - number of tasks"
    print "   P  - 0 or 1 - single or multi-threaded Pyro"
    sys.exit(1)

n_tasks = int(sys.argv[1])
Pyro.config.PYRO_MULTITHREADED = int( sys.argv[2] )

# USE DNS NAMES INSTEAD OF FIXED IP ADDRESSES FROM /etc/hosts
# (see the Userguide "Networking Issues" section).
Pyro.config.PYRO_DNS_URI = True

Pyro.core.initServer()
daemon=Pyro.core.Daemon()

print 'Listening on port', str(daemon.port)

reporter = report( n_tasks )
uri=daemon.connect( reporter, 'reporter' )

pool = []
for i in range(0,n_tasks):
    itask = task( 'Task' + str(i) )
    pool.append( itask )
    uri=daemon.connect( itask, itask.id )

idle = 0
while True:
    n_prev = task.request_count 
    print '.',
    daemon.handleRequests(1.0)
    n_post = task.request_count 
    if n_post > n_prev:
        print '+', n_post, 'request received'
        process(pool)
        idle = 0
    else:
        idle += 1
        sys.stdout.flush()
    if idle > 10:
        break

