#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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

import threading
import datetime
import logging
import time

class batcher( threading.Thread ):
    """A worker thread to process queued job submissions by generating
    and submitting task job scripts in sequential batches. Within each
    batch members are submitted as parallel sub-processes, but we wait
    on all members before proceeding to the next batch in order to avoid
    swamping the system with too many parallel job submission processes."""

    def __init__( self, jobqueue, wireless, batch_size, batch_delay, run_mode, verbose ):
        threading.Thread.__init__(self)
        self.jobqueue = jobqueue
        self.batch_size = int( batch_size )
        self.batch_delay = int( batch_delay )

        self.log = logging.getLogger( 'main' )

        self.quit = False
        self.daemon = True
 
        self.run_mode = run_mode
        self.wireless = wireless
        self.verbose = verbose
        self.thread_id = str(self.getName()) 

    def run( self ):
        # NOTE: Queue.get() blocks if the queue is empty
        # AND: Queue.task_done() doesn't block the producer; it is for
        # queue.join() to block until all queued data is processed.

        while True:
            if self.quit:
                self.log.info(  "Exiting job submission thread" )
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
                self.log.info(  "Submitting batch " + str(i) + " of " + str(n) )
                self.submit( batches.pop(0) )  # index 0 => pop from left
                # only delay if there's another batch left
                if len(batches) > 0:
                    self.log.info(  "  batch delay " )
                    time.sleep( self.batch_delay )
            time.sleep( 1 )

    def submit( self, batch ):
        if self.run_mode == 'simulation':
            for itask in batch:
                self.log.info( 'TASK READY: ' + itask.id )
                itask.incoming( 'NORMAL', itask.id + ' started' )
            return

        before = datetime.datetime.now()
        ps = []
        for itask in batch:
            self.log.info( 'TASK READY: ' + itask.id )
            itask.incoming( 'NORMAL', itask.id + ' submitted' )
            p = itask.submit( overrides=self.wireless.get(itask.id) )
            if p:
                ps.append( (itask,p) ) 
        self.log.info( 'WAITING ON ' + str( len(ps) ) + ' JOB SUBMISSIONS' )
        n_succ = 0
        n_fail = 0
        while len( ps ) > 0:
            for itask, p in ps:
                res = p.poll()
                if res is None:
                    #self.log.info( itask.id + ' still submitting...' )
                    continue
                elif res < 0:
                    self.log.critical( "ERROR: Task " + itask.id + " job submission terminated by signal " + str(res) )
                    itask.incoming( 'CRITICAL', itask.id + ' failed' )
                    n_fail += 1
                elif res > 0:
                    self.log.critical( "ERROR: Task " + itask.id + " job submission failed (" + str(res) + ")" )
                    itask.incoming( 'CRITICAL', itask.id + ' failed' )
                    n_fail += 1
                else:
                    n_succ += 1
                    # set to 'submitted' state if submission succeeds
                    # AND if the task has not already started running
                    # (the submitted state would be skipped if the task
                    # starts running immediately - but this should not
                    # happen due to use of the messsage queue...).
                    #if itask.state.is_submitting():
                ps.remove( (itask,p) )
                self.jobqueue.task_done()
            time.sleep(1)

        after = datetime.datetime.now()
        n_tasks = len(batch)
        self.log.info( """JOB SUBMISSION BATCH COMPLETED
  """ + "Time taken: " + str( after - before ) + """
  """ + str(n_succ) + " of " + str(n_tasks) + """ job submissions succeeded
  """ + str(n_fail) + " of " + str(n_tasks) + " job submissions failed" )

