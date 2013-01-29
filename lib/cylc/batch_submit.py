#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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

import subprocess
import threading
import datetime
import logging
import time

class batcher( threading.Thread ):
    """Submit queued sub-processes in batches: within a batch members
    are submitted in parallel and we wait on all members before
    proceeding to the next batch. This helps to avoid swamping the
    system with too many parallel sub-processes."""

    def __init__( self, name, jobqueue, batch_size, batch_delay, verbose ):
        threading.Thread.__init__(self)
        self.name = name 
        self.jobqueue = jobqueue
        self.batch_size = int( batch_size )
        self.batch_delay = int( batch_delay )

        self.log = logging.getLogger( 'main' )

        # not a daemon thread: shut down when instructed by the main thread
        self.quit = False
 
        self.verbose = verbose
        self.thread_id = str(self.getName()) 

    def idprint( self, msg, err=False ):
        if err:
            self.log.warning(  "ERROR: " + self.name + ": " + msg )
        else:
            self.log.info( self.name + ": " + msg )

    def submit_item( self, item, psinfo ):
        """submit a job by appropriate means, then append the resulting
        process id plus item and an info string to the psinfo list."""

        raise SystemExit( "ERROR: batcher.submit_item() must be overridden" )
 
    def item_failed_hook( self, item, info, msg ):
        """warn of a failed item"""
        # (submitted item supplied in case needed by derived classes)
        self.idprint( info + " " + msg, err=True )

    def run( self ):
        # NOTE: Queue.get() blocks if the queue is empty
        # AND: Queue.task_done() doesn't block the producer; it is for
        # queue.join() to block until all queued data is processed.
        self.log.info(  "Starting " + self.name + " thread" )

        while True:
            if self.quit:
                # TODO: should we process any remaining queue jobs first?
                self.log.info(  "Exiting " + self.name + " thread" )
                break
            batches = []
            batch = []
            # divide current queued jobs into batches
            while self.jobqueue.qsize() > 0:
                if len(batch) < self.batch_size:
                    batch.append( self.jobqueue.get() )
                else:
                    batches.append( batch )
                    batch = []
            if len(batch) > 0:
                batches.append( batch )

            # submit each batch in sequence
            n = len(batches) 
            i = 0
            while len(batches) > 0:
                i += 1
                self.submit( batches.pop(0), i, n )  # index 0 => pop from left
                # only delay if there's another batch left
                if len(batches) > 0:
                    #self.log.info(  "  batch delay " )
                    time.sleep( self.batch_delay )
            time.sleep( 1 )

    def submit( self, batch, i, n ):

        before = datetime.datetime.now()
        psinfo = []

        for itask in batch:
            self.submit_item( itask, psinfo )

        logmsg = 'batch ' + str(i) + '/' + str(n) + ' (' + str( len(psinfo) ) + ' members):'
        for p, item, info in psinfo:
            logmsg += "\n + " + info
        self.idprint( logmsg )

        n_succ = 0
        n_fail = 0
        while len( psinfo ) > 0:
            for data in psinfo:
                p, item, info = data
                res = p.poll()
                if res is None:
                    #self.log.info( info + ' still waiting...' )
                    continue
                elif res < 0:
                    self.item_failed_hook( item, info, "terminated by signal " + str(res) )
                    n_fail += 1
                elif res > 0:
                    self.item_failed_hook( item, info, "failed " + str(res) )
                    n_fail += 1
                else:
                    n_succ += 1
                psinfo.remove( data )
                self.jobqueue.task_done()
            time.sleep(1)

        after = datetime.datetime.now()
        n_tasks = len(batch)

        msg = """batch completed
  """ + "Time taken: " + str( after - before )
        if n_succ == 0:
            msg += """
  All """ + str(n_tasks) + " items FAILED"
        elif n_fail > 0:
            msg += """
  """ + str(n_succ) + " of " + str(n_tasks) + """ items succeeded
  """ + str(n_fail) + " of " + str(n_tasks) + " items FAILED"
        else:
            msg += """
  All """ + str(n_tasks) + " items succeeded"
        self.idprint( msg )

class task_batcher( batcher ):
    """Batched submission of queued tasks"""

    # Note that task state changes as a result of job submission are
    # queued by means of faking incoming task messages - this does not
    # execute in the main thread so we need to avoid making direct task
    # state changes here.

    def __init__( self, name, jobqueue, batch_size, batch_delay, wireless, run_mode, verbose ):
        batcher.__init__( self, name, jobqueue, batch_size, batch_delay, verbose ) 
        self.run_mode = run_mode
        self.wireless = wireless

    def submit( self, batch, i, n ):
        if self.run_mode == 'simulation':
            for itask in batch:
                self.idprint( 'TASK READY: ' + itask.id )
                itask.incoming( 'NORMAL', itask.id + ' started' )
            return
        else:
            batcher.submit( self, batch, i, n )

    def submit_item( self, itask, psinfo ):
        self.log.info( 'TASK READY: ' + itask.id )
        itask.incoming( 'NORMAL', itask.id + ' submitted' )
        p = itask.submit( overrides=self.wireless.get(itask.id) )
        if p:
            psinfo.append( (p, itask, itask.id) ) 

    def item_failed_hook( self, itask, info, msg ):
        itask.incoming( 'CRITICAL', itask.id + ' failed' )
        batcher.item_failed_hook( self, itask, info, msg )

class event_batcher( batcher ):
    """Batched execution of queued task event handlers"""

    def __init__( self, name, jobqueue, batch_size, batch_delay, suite, verbose ):
        batcher.__init__( self, name, jobqueue, batch_size, batch_delay, verbose ) 
        self.suite = suite

    def submit_item( self, item, psinfo ):
        event, handler, taskid, msg = item
        command = " ".join( [handler, event, self.suite, taskid, "'" + msg + "'"] )
        try:
            p = subprocess.Popen( command, shell=True )
        except OSError, e:
            print >> sys.stderr, "ERROR:", e
            self.idprint( "event handler submission failed", err=True )
        else:
            psinfo.append( (p, item, taskid + " " + event) ) 

