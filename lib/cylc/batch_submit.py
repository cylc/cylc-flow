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
import sys
import time

class job_batcher( threading.Thread ):
    """Batch-submit queued subprocesses in parallel, with a delay between batches."""

    def __init__( self, queue_name, jobqueue, batch_size, batch_delay, verbose ):
        threading.Thread.__init__(self)
        self.thread_id = str(self.getName()) 

        self.queue_name = queue_name 
        self.jobqueue = jobqueue
        self.batch_size = int( batch_size )
        self.batch_delay = int( batch_delay )
        self.verbose = verbose

        self.finish_before_exiting = False
        self.log = logging.getLogger( 'main' )
        self.quit = False

    def run( self ):
        """The thread run method."""

        # NOTE: Queue.get() blocks if the queue is empty
        # AND: Queue.task_done() doesn't block the producer; it is for
        # queue.join() to block until all queued data is processed.
        self.log.info(  "Thread Start: " + self.queue_name )

        while True:
            if self.quit:
                if self.finish_before_exiting and self.jobqueue.qsize() > 0:
                    pass
                else:
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
                self.process_batch( batches.pop(0), i, n )  # index 0 => pop from left
                # only delay if there's another batch left
                if len(batches) > 0:
                    #self.log.info(  "  batch delay " )
                    time.sleep( self.batch_delay )
            time.sleep( 1 )

        self.log.info(  "Thread Exit: " + self.queue_name )


    def process_batch( self, batch, i, n ):
        """Submit a batch of jobs in parallel, then wait and collect results."""

        batch_size = len(batch)
        before = datetime.datetime.now()

        # submit each item
        jobs = []
        msg = "batch " + str(i) + '/' + str(n) + " (" + str(len(batch)) + " members):"
        self.log.info( self.queue_name + " " + msg )

        for item in batch:
            jobinfo = \
                    {
                    'p' : None,
                    'out' : None,
                    'err' : None,
                    'data' : None,
                    'descr' : None
                    }
            res = self.submit_item( item, jobinfo )
            if res:
                jobs.append( jobinfo )
            else:
                self.item_failed_hook( jobinfo )

        # determine the success of each job submission in the batch
        n_succ = 0
        n_fail = 0
        while len( jobs ) > 0:
            for jobinfo in jobs:
                res = self.follow_up_item( jobinfo )
                if res is None:
                    # process not done yet
                    continue
                elif res != 0:
                    if res < 0:
                        print >> sys.stderr, "ERROR: process terminated by signal " + str(res)
                    elif res > 0:
                        print >> sys.stderr, "ERROR: process failed: " + str(res)
                    n_fail += 1
                    self.item_failed_hook( jobinfo )
                else:
                    n_succ += 1
                    self.item_succeeded_hook( jobinfo )
                jobs.remove( jobinfo )
                self.jobqueue.task_done()
            time.sleep(1)
        after = datetime.datetime.now()

        msg = """batch completed
  """ + "Time taken: " + str( after - before )
        if n_succ == 0:
            msg += """
  All """ + str(batch_size) + " items FAILED"
        elif n_fail > 0:
            msg += """
  """ + str(n_succ) + " of " + str(batch_size) + """ items succeeded
  """ + str(n_fail) + " of " + str(batch_size) + " items FAILED"
        else:
            msg += """
  All """ + str(batch_size) + " items succeeded"
        self.log.info( self.queue_name + ": " + msg )


    def submit_item( self, item, jobinfo ):
        """
        Submit a single item and update the jobinfo structure above. Any
        data needed by the process follow-up method or item hooks should
        also be added to jobinfo['data'] here.
        """
        raise SystemExit( "ERROR: job_batcher.submit_item() must be overridden" )
 

    def follow_up_item( self, jobinfo ):
        """Determine the result of a single process without blocking."""
        p = jobinfo['p']
        res = p.poll()
        if res is not None:
            jobinfo['out'], jobinfo['err'] = p.communicate()
        return res


    def item_succeeded_hook( self, jobinfo ):
        #self.log.info( jobinfo['descr'] + ' succeeded' )
        pass


    def item_failed_hook( self, jobinfo ):
        self.log.warning( jobinfo['descr'] + ' failed' )


class task_batcher( job_batcher ):
    """Batched task job submission; item is a task proxy object."""

    # Task state changes as a result of job submission are effected by
    # sending fake task messages to be processed in the main thread - we
    # need to avoid making direct task state changes here.

    def __init__( self, queue_name, jobqueue, batch_size, batch_delay, wireless, run_mode, verbose ):
        job_batcher.__init__( self, queue_name, jobqueue, batch_size, batch_delay, verbose ) 
        self.run_mode = run_mode
        self.wireless = wireless
        self.finish_before_exiting = False


    def submit_item( self, itask, jobinfo ):
        jobinfo['descr'] = itask.id + ' job submission'
        try:
            p, launcher = itask.submit( overrides=self.wireless.get(itask.id) )
            jobinfo[ 'p' ] = p
            jobinfo[ 'data' ] = (itask,launcher)
        except Exception, x:
            self.log.critical( str(x) )
            return False
        else:
            return True


    def follow_up_item( self, jobinfo ):
        itask, launcher = jobinfo['data']
        bkg = False
        try:
            if itask.job_sub_method == 'background':
                bkg = True
        except:
            pass

        if bkg:
            p = jobinfo['p']
            # Background tasks echo PID to stdout but do not
            # detach until the job finishes (see comments in
            # job_submission/background.py) - so read one line
            # (PID) but do not wait on the process to finish.
            jobinfo['out'] = p.stdout.readline().rstrip()
            #  p.stderr.readline() blocks until the process
            #  finishes because nothing is written to stderr.
            res = 0
        else: 
            res = job_batcher.follow_up_item( self, jobinfo )
        return res


    def item_succeeded_hook( self, jobinfo ):
        job_batcher.item_succeeded_hook( self, jobinfo )
        itask,launcher = jobinfo['data']
        itask.incoming('NORMAL', itask.id + ' submission succeeded' )
        p = jobinfo['p']
        out = jobinfo['out']
        err = jobinfo['err']
        if hasattr(launcher, 'get_id'):
            # Extract the job submit ID from submission command output
            submit_method_id = launcher.get_id( out, err )
            if submit_method_id:
                itask.incoming('NORMAL', itask.id + ' submit_method_id=' + submit_method_id )


    def item_failed_hook( self, jobinfo ):
        job_batcher.item_failed_hook( self, jobinfo )
        out = jobinfo['out']
        err = jobinfo['err']
        itask,launcher = jobinfo['data']
        if out:
            itask.incoming( 'NORMAL', out )
        if err:
            itask.incoming( 'WARNING', err )
        itask.incoming( 'CRITICAL', itask.id + ' submission failed' )
 


class event_batcher( job_batcher ):
    """Batched execution of task event handlers; item is (event-label,
    handler, task-id, message). We do not capture the output of event
    handlers as doing so could block the thread."""

    def __init__( self, queue_name, jobqueue, batch_size, batch_delay, suite, verbose ):
        job_batcher.__init__( self, queue_name, jobqueue, batch_size, batch_delay, verbose ) 
        self.suite = suite
        self.finish_before_exiting = True


    def submit_item( self, item, jobinfo ):
        event, handler, taskid, msg = item
        jobinfo['descr'] = taskid + ' ' + event + ' handler'
        command = " ".join( [handler, "'" + event + "'", self.suite, taskid, "'" + msg + "'"] )
        try:
            jobinfo['p'] = subprocess.Popen( command, shell=True )
        except OSError, e:
            print >> sys.stderr, "ERROR:", e
            self.log.warning(  "ERROR: " + self.queue_name + ": failed to invoke event handler" )
            return False
        else:
            return True



class poll_and_kill_batcher( job_batcher ):
    """Batched submission of task poll and kill commands."""

    def __init__( self, queue_name, jobqueue, batch_size, batch_delay, run_mode, verbose ):
        job_batcher.__init__( self, queue_name, jobqueue, batch_size, batch_delay, verbose ) 
        self.run_mode = run_mode
        self.finish_before_exiting = False


    def process_batch( self, batch, i, n ):
        # TODO - get rid of simulation checks in here
        if self.run_mode == 'simulation':
            # no real jobs to poll in simulation mode
            return
        else:
            job_batcher.process_batch( self, batch, i, n )


    def submit_item( self, item, jobinfo ):
        command, itask, jtype = item
        jobinfo['data'] = itask
        jobinfo['jtype'] = jtype
        jobinfo['descr'] = 'job ' + jtype
        try:
            jobinfo['p'] = subprocess.Popen( command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
        except OSError, e:
            print >> sys.stderr, "ERROR:", e
            self.log.warning(  "ERROR: " + self.queue_name + ": task poll command invocation failed" )
            return False
        else:
            return True


    def item_failed_hook( self, jobinfo ):
        job_batcher.item_failed_hook( self, jobinfo )
        print >> sys.stderr, jobinfo['err']
        print jobinfo['out']
        itask = jobinfo['data']
        itask.incoming( 'CRITICAL', jobinfo['jtype'] + ' command failed' )
 

    def item_succeeded_hook( self, jobinfo ):
        job_batcher.item_succeeded_hook( self, jobinfo )
        itask = jobinfo['data']
        if jobinfo['jtype'] == 'poll':
            # get-task-status prints a standard task message to stdout
            itask.incoming( 'NORMAL', jobinfo['out'].strip() )
        else:
            # TODO - just log?
            itask.incoming( 'NORMAL', jobinfo['jtype'] + ' command succeeded' )
        if jobinfo['err']:
            # TODO - just log?
            print >> sys.stderr, jobinfo['err']

