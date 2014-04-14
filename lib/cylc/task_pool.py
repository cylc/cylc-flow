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
import Queue
from batch_submit import task_batcher
from task_types import task
from broker import broker
import flags
from Pyro.errors import NamingError, ProtocolError
import cylc.rundb
from CylcError import SchedulerError
from broadcast import broadcast

# All new task proxies (including spawned ones) are added first to the
# runahead pool, which does not participate in dependency matching and 
# is not visible in the GUI. Tasks are then released to the task pool if
# not beyond the current runahead limit.

# TODO ISO -
# Spawn-on-submit means a only one waiting instance of each task exists,
# in the pool, so if a new stop cycle is set we just need to check
# waiting pool tasks against the new stop cycle.

# restart: runahead tasks are all in the 'waiting' state and will be
# reloaded as such, on restart, into the runahead pool.


class pool(object):
    def __init__( self, suite, db, stop_tag, config, pyro, log, run_mode ):
        self.pyro = pyro
        self.run_mode = run_mode
        self.log = log
        self.qconfig = config.cfg['scheduling']['queues']
        self.stop_tag = stop_tag
        self.reconfiguring = False
        self.db = db

        self.runahead_limit = config.get_runahead_limit()

        self.runahead_pool = {}
        self.myq = {}
        self.queues = {}
        self.assign_queues()

        self.pool_list = []
        self.rhpool_list = []
        self.pool_changed = []
        self.rhpool_changed = []

        self.wireless = broadcast( config.get_linearized_ancestors() )
        self.pyro.connect( self.wireless, 'broadcast_receiver')

        self.broker = broker()

        self.jobqueue = Queue.Queue()

        self.worker = task_batcher( 'Job Submission', self.jobqueue,
                config.cfg['cylc']['job submission']['batch size'],
                config.cfg['cylc']['job submission']['delay between batches'],
                self.wireless, self.run_mode )

        self.orphans = []
        self.task_name_list = self.config.get_task_name_list()

        self.worker.start()


    def assign_queues( self ):
        """self.myq[taskname] = qfoo"""
        self.myq = {}
        for queue in self.qconfig:
            for taskname in self.qconfig[queue]['members']:
                self.myq[taskname] = queue



    def add( self, itask ):

        if self.id_exists( itask.id ):
            # e.g. an inserted task caught up with an existing one with the same ID.
            self.log.warning( itask.id + ' cannot be added: task ID already exists' )
            return False

        # TODO ISO - no longer needed due to recurrence bounds?
        if itask.stop_c_time and itask.c_time > itask.stop_c_time:
            self.log.warning( itask.id + ' not adding to pool: task beyond its own stop cycle' )
            return False

        # check cycle stop or hold conditions
        if self.stop_tag and itask.c_time > self.stop_tag:
            itask.log( 'DEBUG', "not adding (beyond suite stop cycle) " + str(self.stop_tag) )
            itask.reset_state_held()
            return

        # TODO ISO -restore suite hold functionality
        #if self.hold_time and itask.c_time > self.hold_time:
        #    itask.log( 'DEBUG', "not adding (beyond suite hold cycle) " + str(self.hold_time) )
        #    itask.reset_state_held()
        #    return

        # hold tasks with future triggers beyond the final cycle time
        if self.task_has_future_trigger_overrun( itask ):
            itask.log( "NORMAL", "not adding (future trigger beyond stop cycle)" )
            self.held_future_tasks.append( itask.id )
            itask.reset_state_held()
            return

        self.runahead_pool[itask.id] = itask

        self.rhpool_changed = True

        return True


    def release_runahead_tasks( self ):

        # compute runahead base: the oldest task not succeeded or failed
        # (excludes finished and includes runahead-limited tasks so a low limit cannot stall a suite.
        runahead_base = None
        for itask in self.get_tasks(all=True):
            if itask.state.is_currently('failed', 'succeeded'):
                continue
            if not runahead_base or itask.c_time < runahead_base:
                runahead_base = itask.c_time

        if self.runahead_limit and runahead_base:
            for itask in self.runahead_pool.values():
                if itask.c_time - self.runahead_limit <= runahead_base:
                    # release task to the appropriate queue
                    queue = self.myq[itask.name]
                    if queue not in self.queues:
                        self.queues[queue] = {}
                    self.queues[queue][itask.id] = itask
                    self.pool_changed = True
                    flags.pflag = True
                    itask.log('DEBUG', "released to the task pool" )
                    del self.runahead_pool[itask.id]
                    self.rhpool_changed = True
                    try:
                        self.pyro.connect( itask.message_queue, itask.id )
                    except Exception, x:
                        if flags.debug:
                            raise
                        print >> sys.stderr, x
                        self.log.warning( itask.id + ' cannot be added (use --debug and see stderr)' )
                        return False


    def remove( self, itask, reason=None ):
        if itask.id in self.runahead_pool:
            del self.runahead_pool[itask.id]
            self.rhpool_changed = True
            return

        try:
            self.pyro.disconnect( itask.message_queue )
        except NamingError, x:
            print >> sys.stderr, x
            self.log.critical( itask.id + ' cannot be removed (task not found)' )
            return
        except Exception, x:
            print >> sys.stderr, x
            self.log.critical( itask.id + ' cannot be removed (unknown error)' )
            return
        # remove from queue
        queue = self.myq[itask.name]
        del self.queues[queue][itask.id]
        self.pool_changed = True
        msg = "task proxy removed"
        if reason:
            msg += " (" + reason + ")"
        itask.log( 'DEBUG', msg )
        del itask



    def get_tasks( self, all=False ):
        """ Return the current list of task proxies."""

        # Regenerate the task lists on demand only if they have changed
        # (only necessary if computing the list takes significant time?)

        # May not be necessary at all once we centralize all pool ops?

        if self.pool_changed:
            self.pool_changed = False
            self.pool_list = []
            for queue in self.queues:
                for id,t in self.queues[queue].items():
                    self.pool_list.append( t )
        
        if all:
            if self.rhpool_changed: 
                self.rhpool_changed = False
                self.rhpool_list = self.runahead_pool.values()
 
            return self.rhpool_list + self.pool_list
        else:
            return self.pool_list


    def id_exists( self, id ):
        """Check if task id is in the runahead_pool or pool"""
        if id in self.runahead_pool:
            return True
        for queue in self.queues:
            if id in self.queues[queue]:
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
            tasks = self.queues[queue].values()
            if n_limit:
                for itask in tasks:
                    if itask.state.is_currently('ready','submitted','running'):
                        n_active += 1
                n_release = n_limit - n_active

            # 2.2) release queued tasks if not limited or if manually forced
            for itask in tasks:
                if not itask.state.is_currently( 'queued' ):
                    continue
                if itask.manual_trigger or not n_limit or n_release > 0:
                    # manual release, or no limit, or not currently limited
                    n_release -= 1
                    readytogo.append(itask)
                    if itask.manual_trigger:
                        itask.reset_manual_trigger()
                # else leaved queued

        n_ready = len(readytogo)
        if n_ready > 0:
            self.log.debug( '%d task(s) ready' % n_ready )
            for itask in readytogo:
                itask.set_state_ready()
                self.jobqueue.put( itask )

        return readytogo

    def task_has_future_trigger_overrun( self, itask ):
        # check for future triggers extending beyond the final cycle
        if not self.stop_tag:
            return False
        for pct in set(itask.prerequisites.get_target_tags()):
            try:
                if pct > self.stop_tag:
                    return True
            except:
                raise
                # pct invalid cycle time => is an asynch trigger
                pass
        return False


    # TODO ISO - adapt to iso:
    def set_runahead( self, hours=None ):
        if hours:
            self.log.info( "setting runahead limit to " + str(hours) )
            self.runahead_limit = int(hours)
        else:
            # No limit
            self.log.warning( "setting NO runahead limit" )
            self.runahead_limit = None


    def get_min_ctime( self ):
        """Return the minimum cycle currently in the pool."""
        cycles = [ t.c_time for t in self.get_tasks() ]
        minc = None
        if cycles:
            minc = min(cycles)
        return minc


    def get_max_ctime( self ):
        """Return the maximum cycle currently in the pool."""
        cycles = [ t.c_time for t in self.get_tasks() ]
        maxc = None
        if cycles:
            maxc = max(cycles)
        return maxc



    def reconfigure( self, config ):

        self.reconfiguring = True

        self.runahead_limit = config.get_runahead_limit()

        # reassign live tasks from the old queues to the new.
        # self.queues[queue][id] = task
        self.qconfig = config.cfg['scheduling']['queues']
        self.assign_queues()
        self.new_queues = {}
        for queue in self.queues:
            for id,itask in self.queues[queue].items():
                myq = self.myq[itask.name]
                if myq not in self.new_queues:
                    self.new_queues[myq] = {}
                self.new_queues[myq][id] = itask
        self.queues = self.new_queues

        for itask in self.get_tasks(all=True):
            itask.reconfigure_me = True

        # find any old tasks that have been removed from the suite
        old_task_name_list = self.task_name_list
        self.task_name_list = config.get_task_name_list()
        for name in old_task_name_list:
            if name not in new_task_list:
                self.orphans.append(name)
        # adjust the new suite config to handle the orphans
        config.adopt_orphans( self.orphans )
        

    def reload_taskdefs( self ):
        found = False
        for itask in self.get_tasks(all=True):
            if itask.state.is_currently('running'):
                # do not reload running tasks as some internal state
                # (e.g. timers) not easily cloneable at the moment,
                # and it is possible to make changes to the task config
                # that would be incompatible with the running task.
                if itask.reconfigure_me:
                    found = True
                continue
            if itask.reconfigure_me:
                itask.reconfigure_me = False
                if itask.name in self.orphans:
                    # orphaned task
                    if itask.state.is_currently('waiting', 'queued', 'submit-retrying', 'retrying'):
                        # if not started running yet, remove it.
                        self.pool.remove( itask, '(task orphaned by suite reload)' )
                    else:
                        # set spawned already so it won't carry on into the future
                        itask.state.set_spawned()
                        self.log.warning( 'orphaned task will not continue: ' + itask.id  )
                else:
                    self.log.info( 'RELOADING TASK DEFINITION FOR ' + itask.id  )
                    new_task = self.config.get_task_proxy( itask.name, itask.tag, itask.state.get_status(), None, itask.startup, submit_num=self.db.get_task_current_submit_num(itask.name, itask.tag), exists=self.db.get_task_state_exists(itask.name, itask.tag) )
                    # set reloaded task's spawn status
                    if itask.state.has_spawned():
                        new_task.state.set_spawned()
                    else:
                        new_task.state.set_unspawned()
                    # succeeded tasks need their outputs set completed:
                    if itask.state.is_currently('succeeded'):
                        new_task.reset_state_succeeded(manual=False)
                    self.pool.remove( itask, '(suite definition reload)' )
                    self.pool.add( new_task )

        self.reconfiguring = found


    def no_active_tasks( self ):
        for itask in self.get_tasks():
            if itask.state.is_currently('running', 'submitted'):
                return False
        return True


    def release_tasks( ids ):
        for itask in self.get_tasks():
            if itask.id in ids and itask.state.is_currently('held'):
                itask.reset_state_waiting()


    def poll_tasks( ids ):
        for itask in self.get_tasks():
            if itask.id in ids:
                # (state check done in task module)
                itask.poll()

    def kill_tasks( ids ):
        for itask in self.get_tasks():
            if itask.id in ids:
                # (state check done in task module)
                itask.kill()


    def hold_all_tasks( self ):
        self.log.info( "Holding all waiting or queued tasks now")
        for itask in self.get_tasks():
            if itask.state.is_currently('queued','waiting','submit-retrying', 'retrying'):
                itask.reset_state_held()

    def release_all_tasks( self ):
        # TODO ISO - check that we're not still holding tasks beyond suite
        # stop time (no point as finite-range tasks now disappear beyond
        # their stop time).
        for itask in self.get_tasks():
            if itask.state.is_currently('held'):
                #if self.stop_tag and itask.c_time > self.stop_tag:
                #    # this task has passed the suite stop time
                #    itask.log( 'NORMAL', "Not releasing (beyond suite stop cycle) " + str(self.stop_tag) )
                #elif itask.stop_c_time and itask.c_time > itask.stop_c_time:
                #    # this task has passed its own stop time
                #    itask.log( 'NORMAL', "Not releasing (beyond task stop cycle) " + str(itask.stop_c_time) )
                #else:
                # release this task
                itask.reset_state_waiting()

        # TODO - write a separate method for cancelling a stop time:
        #if self.stop_tag:
        #    self.log.warning( "UNSTOP: unsetting suite stop time")
        #    self.stop_tag = None


    def get_failed_tasks( self ):
        failed = []
        for itask in self.get_tasks():
            if itask.state.is_currently('failed', 'submit-failed' ):
                failed.append( itask )
        return failed


    def any_task_failed( self ):
        for itask in self.get_tasks():
            if itask.state.is_currently('failed', 'submit-failed' ):
                return True
        return False


    def match_dependencies( self ):
        # run time dependency negotiation: tasks attempt to get their
        # prerequisites satisfied by other tasks' outputs.
        # BROKERED NEGOTIATION is O(n) in number of tasks.

        self.broker.reset()

        self.broker.register( self.get_tasks() )

        for itask in self.get_tasks():
            # try to satisfy itask if not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate( itask )

        # TODO - RESTORE THE FOLLOWING FOR repeating_async TASKS:
        #for itask in self.get_tasks():
        #    if not itask.not_fully_satisfied():
        #        itask.check_requisites()


    def process_queued_task_messages( self ):
        state_recorders = []
        state_updaters = []
        event_recorders = []
        other = []

        for itask in self.get_tasks():
            itask.process_incoming_messages()
            # if incoming messages have resulted in new database operations grab them
            if itask.db_items:
                opers = itask.get_db_ops()
                for oper in opers:
                    if isinstance(oper, cylc.rundb.UpdateObject):
                        state_updaters += [oper]
                    elif isinstance(oper, cylc.rundb.RecordStateObject):
                        state_recorders += [oper]
                    elif isinstance(oper, cylc.rundb.RecordEventObject):
                        event_recorders += [oper]
                    else:
                        other += [oper]

        #precedence is record states > update_states > record_events > anything_else
        db_ops = state_recorders + state_updaters + event_recorders + other
        # compact the set of operations
        if len(db_ops) > 1:
            db_opers = [db_ops[0]]
            for i in range(1,len(db_ops)):
                if db_opers[-1].s_fmt == db_ops[i].s_fmt:
                    if isinstance(db_opers[-1], cylc.rundb.BulkDBOperObject):
                        db_opers[-1].add_oper(db_ops[i])
                    else:
                        new_oper = cylc.rundb.BulkDBOperObject(db_opers[-1])
                        new_oper.add_oper(db_ops[i])
                        db_opers.pop(-1)
                        db_opers += [new_oper]
                else:
                    db_opers += [db_ops[i]]
        else:
            db_opers = db_ops

        # record any broadcast settings to be dumped out
        if self.wireless:
            if self.wireless.new_settings:
                db_ops = self.wireless.get_db_ops()
                for d in db_ops:
                    db_opers += [d]

        for d in db_opers:
            if self.db.c.is_alive():
                self.db.run_db_op(d)
            elif self.db.c.exception:
                raise self.db.c.exception
            else:
                raise SchedulerError( 'An unexpected error occurred while writing to the database' )


    def force_spawn( self, itask ):
        # TODO - THIS SHOULD BE IN task.py
        if itask.state.has_spawned():
            return None
        itask.state.set_spawned()
        itask.log( 'DEBUG', 'forced spawning')
        new_task = itask.spawn( 'waiting' )
        if new_task and self.pool.add( new_task ):
            return new_task
        else:
            return None


    def spawn_tasks( self ):
        for itask in self.get_tasks():
            if itask.ready_to_spawn():
                self.force_spawn( itask )

