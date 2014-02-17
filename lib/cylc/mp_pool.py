#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import flags
if flags.MP_USE_PROCESS_POOL:
    from multiprocessing import Pool
else:
    from multiprocessing.pool import ThreadPool as Pool
from collections import deque
import subprocess
import logging
import time
 
"""Process or thread pool for shell commands and asynchronous output capture."""

CAPTURE_ALL=0
CAPTURE_ONE=1
CAPTURE_NIL=2

def execute( command, capture, close_fds ):
    """Execute a shell command and optionally capture its output and exit status."""
    result = { 'EXIT' : None, 'OUT' : None, 'ERR' : None }
    if capture != CAPTURE_NIL:
        oe = subprocess.PIPE
    else:
        oe = None
    try:
        p = subprocess.Popen( command, stdout=oe, stderr=oe, shell=True, close_fds=close_fds )
    except Exception, e:
        result[ 'EXIT' ] = 1
        result[ 'ERR'  ] = str(e)
    else:
        if capture == CAPTURE_NIL: 
            # ignore output
            pass
        elif capture == CAPTURE_ONE:
            # capture first line of stdout only
            result['EXIT'] = 0
            result['OUT' ] = p.stdout.readline().rstrip()
        elif capture == CAPTURE_ALL:
            # capture all output
            result['EXIT'] = p.wait()
            if result['EXIT'] is not None:
                result['OUT'], result['ERR'] = p.communicate()
    return result

class mp_pool( object ):
    def __init__( self ):
        self.pool = Pool(processes=flags.MP_NPROC)
        self.log = logging.getLogger( 'main' )
        self.results = deque()
        self.finished = False

    def put( self, command, callback=None, capture_one=False, close_fds=False ):
        """Queue a command, and capture results if a callback is given."""
        if self.finished:
            self.log.warning( 'rejected (worker pool done):\n  ' + command )
            return False
        if callback:
            if capture_one:
                capture = CAPTURE_ONE
            else:
                capture = CAPTURE_ALL
        else:
            capture = CAPTURE_NIL
        res = self.pool.apply_async( execute, (command,capture,close_fds) )
        if callback:
            self.results.append( (res,callback) )
        return True

    def check_results( self ):
        """Loop once through the async results and see if they are done yet."""
        not_done = deque()
        while self.results:
            res, callback = self.results.popleft()
            if res.ready():
                callback( res.get() )
            else:
                not_done.append( (res,callback) )
            time.sleep(.1)
        self.results = not_done

    def shutdown( self, flush=False ):
        """Terminate the pool immediately or after queued jobs are done."""
        self.finished = True
        if flush:
            self.pool.close()
        else:
            self.pool.terminate()
        self.pool.join()

