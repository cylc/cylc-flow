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

import Queue
from batch_submit import batcher
from task_types import task
import flags

class pool(object):
    def __init__( self, suite, config, wireless, pyro, log, run_mode, verbose, debug=False ):
        self.pyro = pyro
        self.run_mode = run_mode
        self.log = log
        self.verbose = verbose
        self.debug = debug
        self.qconfig = config['scheduling']['queues'] 
        self.config = config
        self.assign()
        self.wireless = wireless

        self.jobqueue = Queue.Queue()

        self.worker = batcher( self.jobqueue, self.wireless,
                config['cylc']['job submission']['batch size'],
                config['cylc']['job submission']['delay between batches'],
                self.run_mode, self.verbose )

        if self.verbose:
            print "Starting job submission worker thread"
        self.worker.start()

    def assign( self, reload=False ):
        # self.myq[taskname] = 'foo'
        # self.queues['foo'] = [live tasks in queue foo]

        self.myq = {}
        for queue in self.qconfig:
            for taskname in self.qconfig[queue]['members']:
                self.myq[taskname] = queue

        if not reload:
            self.queues = {}
        else:
            # reassign live tasks from the old queues to the new
            self.new_queues = {}
            for queue in self.queues:
                for itask in self.queues[queue]:
                    myq = self.myq[itask.name]
                    if myq not in self.new_queues:
                        self.new_queues[myq] = [itask]
                    else:
                        self.new_queues[myq].append( itask )
            self.queues = self.new_queues

    def add( self, itask ):
        try:
            self.pyro.connect( itask.message_queue, itask.id )
        except NamingError, x:
            # Attempted insertion of a task that already exists.
            print >> sys.stderr, x
            self.log.critical( itask.id + ' CANNOT BE INSERTED (already exists)' )
            return
        except Exception, x:
            print >> sys.stderr, x
            self.log.critical( itask.id + ' CANNOT BE INSERTED (unknown error)' )
            return

        # add task to the appropriate queue
        queue = self.myq[itask.name]
        if queue not in self.queues:
            self.queues[queue] = [itask]
        else:
            self.queues[queue].append(itask)
        flags.pflag = True
        itask.log('DEBUG', "task proxy inserted" )

    def remove( self, task, reason ):
        # remove a task from the pool
        try:
            self.pyro.disconnect( task.message_queue )
        except NamingError, x:
            # Attempted removal of a task that does not exist.
            print >> sys.stderr, x
            self.log.critical( task.id + ' CANNOT BE REMOVED (no such task)' )
            return
        except Exception, x:
            print >> sys.stderr, x
            self.log.critical( task.id + ' CANNOT BE REMOVED (unknown error)' )
            return
        task.prepare_for_death()
        # remove task from its queue
        queue = self.myq[task.name]
        self.queues[queue].remove( task )
        task.log( 'DEBUG', "task proxy removed (" + reason + ")" )
        del task

    def get_tasks( self ):
        tasks = []
        for queue in self.queues:
            tasks += self.queues[queue]
        #tasks.sort() # sorting any use here?
        return tasks

    def process( self ):
        readytogo = []
        for queue in self.queues:
            n_active = 0
            n_limit = self.qconfig[queue]['limit']
            for itask in self.queues[queue]:
                if n_limit:
                    # there is a limit on this queue
                    if (itask.state.is_currently('submitted') or
                        itask.state.is_currently('running') or
                        itask.state.is_currently('submitting')):
                        # count active tasks in this queue
                        n_active += 1
                    # compute difference from the limit
                    n_release = n_limit - n_active
                    if n_release <= 0:
                        # the limit is currently full
                        continue
            for itask in self.queues[queue]:
                if itask.ready_to_run():
                    if n_limit:
                        if n_release > 0:
                            n_release -= 1
                            readytogo.append(itask)
                        else:
                            # (direct task state reset ok: this executes in the main thread)
                            itask.reset_state_queued()
                    else:
                        readytogo.append(itask)

        if len(readytogo) == 0:
            if self.verbose:
                print "(No tasks ready to run)"
            return []

        print
        n_tasks = len(readytogo)
        print n_tasks, 'TASKS READY TO BE SUBMITTED'

        for itask in readytogo:
            # (direct task state reset ok: this executes in the main thread)
            itask.reset_state_submitting()
            self.jobqueue.put( itask )

        return readytogo

