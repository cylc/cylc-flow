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

import sys
from task_types import task
from mp_pool import mp_pool
import flags
from Pyro.errors import NamingError, ProtocolError
from cycle_time import ctime_gt

class pool(object):
    def __init__( self, suite, config, wireless, pyro, log, run_mode ):
        self.pyro = pyro
        self.run_mode = run_mode
        self.log = log
        self.qconfig = config.cfg['scheduling']['queues']
        self.config = config
        self.assign()
        self.wireless = wireless
        self.workers = mp_pool() 

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
        """
        Add the given new task if one with the same ID does not already
        exist, and if the task has not passed its own stop cycle (if it
        has a stop cycle).
        """
        if itask.stop_c_time and ctime_gt( itask.c_time, itask.stop_c_time ):
            self.log.warning( itask.id + ' not adding to pool: task beyond its own stop cycle' )
            return False

        if self.id_exists( itask.id ):
            # This can happen by manual insertion of task that is
            # already in the pool, or if an inserted cycling task
            # catches up with an existing one with the same ID.
            self.log.warning( itask.id + ' cannot be added: task ID already exists' )
            return False
        # Connect the new task to the pyro daemon
        try:
            self.pyro.connect( itask.message_queue, itask.id )
        except Exception, x:
            if flags.debug:
                raise
            print >> sys.stderr, x
            self.log.warning( itask.id + ' cannot be added (use --debug and see stderr)' )
            return False
        # add the new task to the appropriate queue
        queue = self.myq[itask.name]
        if queue not in self.queues:
            self.queues[queue] = [itask]
        else:
            self.queues[queue].append(itask)
        flags.pflag = True
        itask.log('DEBUG', "task proxy added to the pool" )
        return True

    def remove( self, task, reason=None ):
        # remove a task from the pool
        try:
            self.pyro.disconnect( task.message_queue )
        except NamingError, x:
            print >> sys.stderr, x
            self.log.critical( task.id + ' cannot be removed (task not found)' )
            return
        except Exception, x:
            print >> sys.stderr, x
            self.log.critical( task.id + ' cannot be removed (unknown error)' )
            return
        task.prepare_for_death()
        # remove task from its queue
        queue = self.myq[task.name]
        self.queues[queue].remove( task )
        msg = "task proxy removed"
        if reason:
            msg += " (" + reason + ")"
        task.log( 'DEBUG', msg )
        del task

    def get_tasks( self ):
        """Return a list of all task proxies"""
        tasks = []
        for queue in self.queues:
            tasks += self.queues[queue]
        #tasks.sort() # sorting any use here?
        return tasks

    def id_exists( self, id ):
        """Check if a task with the given ID is in the pool"""
        for queue in self.queues:
            for task in self.queues[queue]:
                if task.id == id:
                    return True
        return False

    def process( self ):
        """
        1) queue tasks that are ready to run (prerequisites satisfied,
        clock-trigger time up) or if their manual trigger flag is set.

        2) then submit queued tasks if their queue limit has not been
        reached or their manual trigger flag is set.

        The "queued" task state says the task will submit as soon as its
        internal queue allows (or immediately if manually triggered first).

        Use of "cylc trigger" sets a task's manual trigger flag. Then,
        below, an unqueued task will be queued whether or not it is
        ready to run; and a queued task will be submitted whether or not
        its queue limit has been reached. The flag is immediately unset
        after use so that two manual trigger ops are required to submit
        an initially unqueued task that is queue-limited.
        """

        # (task state resets below are ok as this executes in main thread)

        # 1) queue unqueued tasks that are ready to run or manually forced
        for itask in self.get_tasks():
            if not itask.state.is_currently( 'queued' ):
                # only need to check that unqueued tasks are ready
                if itask.manual_trigger or itask.ready_to_run():
                    # queue the task
                    itask.set_state_queued()
                    if itask.manual_trigger:
                        itask.reset_manual_trigger()

        # 2) submit queued tasks if manually forced or not queue-limited
        readytogo = []
        for queue in self.queues:
            # 2.1) count active tasks and compare to queue limit
            n_active = 0
            n_release = 0
            n_limit = self.qconfig[queue]['limit']
            if n_limit:
                for itask in self.queues[queue]:
                    if itask.state.is_currently('ready','submitted','running'):
                        n_active += 1
                n_release = n_limit - n_active

            # 2.2) release queued tasks if not limited or if manually forced
            for itask in self.queues[queue]:
                if not itask.state.is_currently( 'queued' ):
                    continue
                if itask.manual_trigger or not n_limit or n_release > 0:
                    # manual release, or no limit, or not currently limited
                    n_release -= 1
                    readytogo.append(itask)
                    if itask.manual_trigger:
                        itask.reset_manual_trigger()
                # else leaved queued

        self.log.debug( '%d task(s) ready' % len(readytogo) )

        for itask in readytogo:
            if self.run_mode == 'simulation':
                itask.job_submission_succeeded( '','' )
                continue
            if self.workers.finished:
                continue
            try:
                command = itask.get_command( overrides=self.wireless.get(itask.id))
            except Exception, e:
                # TODO - is this the right response?
                itask.job_submission_failed( err=str(e) )
            else:
                if self.workers.put( command, itask.job_submission_result,\
                        itask.job_sub_method_name=='background', True ):
                    # TODO - set_state_ready() should increment sub number etc.
                    itask.set_state_ready()

        return readytogo

# close_fds=True job submission: required to prevent the process from hanging on to
# the file descriptor that was used to write the job script, the root
# cause of the random "text file busy" error.
 
# Background jobs echo PID to stdout but do not detach. Read one line to
# get PID then don't wait on the process.
#  p.stderr.readline() blocks until the process
#  finishes because nothing is written to stderr.

