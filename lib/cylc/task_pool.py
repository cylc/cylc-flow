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
import TaskID
from batch_submit import task_batcher
from task_types import task
from broker import broker
import flags
from Pyro.errors import NamingError, ProtocolError
import cylc.rundb
from cylc.cycling.loader import (
    get_point, get_interval, get_interval_cls, ISO8601_CYCLING_TYPE)
from CylcError import SchedulerError, TaskNotFoundError
from prerequisites.plain_prerequisites import plain_prerequisites
from broadcast import broadcast

# All new task proxies (including spawned ones) are added first to the
# runahead pool, which does not participate in dependency matching and 
# is not visible in the GUI. Tasks are then released to the task pool if
# not beyond the current runahead limit.

# The check_stop() and remove_spent_cycling_task() have to consider
# tasks in the runahead pool too.

# TODO ISO -
# Spawn-on-submit means a only one waiting instance of each task exists,
# in the pool, so if a new stop cycle is set we just need to check
# waiting pool tasks against the new stop cycle.

# restart: runahead tasks are all in the 'waiting' state and will be
# reloaded as such, on restart, into the runahead pool.


class pool(object):

    def __init__( self, suite, db, stop_point, config, pyro, log, run_mode ):
        self.pyro = pyro
        self.run_mode = run_mode
        self.log = log
        self.qconfig = config.cfg['scheduling']['queues']
        self.stop_point = stop_point
        self.reconfiguring = False
        self.db = db

        self.custom_runahead_limit = config.get_custom_runahead_limit()
        self.minimum_runahead_limit = config.get_minimum_runahead_limit()
        self.max_num_active_cycle_points = (
            config.get_max_num_active_cycle_points())
        self._prev_runahead_base_point = None
        self._prev_runahead_sequence_points = None

        self.config = config

        self.pool = {}
        self.runahead_pool = {}
        self.myq = {}
        self.queues = {}
        self.assign_queues()

        self.pool_list = []
        self.rhpool_list = []
        self.pool_changed = []
        self.rhpool_changed = []

        self.held_future_tasks = []

        self.wireless = broadcast( config.get_linearized_ancestors() )
        self.pyro.connect( self.wireless, 'broadcast_receiver')

        self.broker = broker()

        self.jobqueue = Queue.Queue()

        self.worker = task_batcher( 'Job Submission', self.jobqueue,
                config.cfg['cylc']['job submission']['batch size'],
                config.cfg['cylc']['job submission']['delay between batches'],
                self.wireless, self.run_mode )

        self.orphans = []
        self.task_name_list = config.get_task_name_list()

        self.worker.start()


    def assign_queues( self ):
        """self.myq[taskname] = qfoo"""
        self.myq = {}
        for queue in self.qconfig:
            for taskname in self.qconfig[queue]['members']:
                self.myq[taskname] = queue


    def add_to_runahead_pool( self, itask ):
        """Add a new task to the runahead pool if possible.
        Tasks whose recurrences allow them to spawn beyond the suite
        stop point are added to the pool in the held state, ready to be
        released if the suite stop point is changed."""

        # do not add if a task with the same ID already exists
        # e.g. an inserted task caught up with an existing one
        if self.id_exists( itask.id ):
            self.log.warning( itask.id + ' cannot be added to pool: task ID already exists' )
            del itask
            return False

        # do not add if an inserted task is beyond its own stop point
        # (note this is not the same as recurrence bounds)
        if itask.stop_c_time and itask.c_time > itask.stop_c_time:
            self.log.info( itask.id + ' not adding to pool: beyond task stop cycle' )
            del itask
            return False
 
        # add in held state if beyond the suite stop point
        if self.stop_point and itask.c_time > self.stop_point:
            itask.log( 'NORMAL', "holding (beyond suite stop point) " + str(self.stop_point) )
            itask.reset_state_held()

        # add in held state if beyond the suite hold point
        # TODO ISO -restore this functionality
        #elif self.hold_time and itask.c_time > self.hold_time:
        #    itask.log( 'NORMAL', "holding (beyond suite hold point) " + str(self.hold_time) )
        #    itask.reset_state_held()

        # add in held state if a future trigger goes beyond the suite stop point
        # (note this only applies to tasks below the suite stop point themselves)
        elif self.task_has_future_trigger_overrun( itask ):
            itask.log( "NORMAL", "holding (future trigger beyond stop point)" )
            self.held_future_tasks.append( itask.id )
            itask.reset_state_held()

        # add to the runahead pool
        self.runahead_pool.setdefault(itask.c_time, {})
        self.runahead_pool[itask.c_time][itask.id] = itask
        self.rhpool_changed = True
        return True


    def get_task_proxy( self, *args, **kwargs ):
        return self.config.get_task_proxy(*args, **kwargs)


    def release_runahead_tasks( self ):

        # compute runahead base: the oldest task not succeeded or failed
        # (excludes finished and includes runahead-limited tasks so a
        # low limit cannot stall the suite).

        if not self.runahead_pool:
            return

        limit = self.max_num_active_cycle_points

        points = []
        for point, itasks in sorted(
                self.get_tasks_by_point(all=True).items()):
            has_unfinished_itasks = False
            for itask in itasks:
                if not itask.state.is_currently('failed', 'succeeded'):
                    has_unfinished_itasks = True
                    break
            if not points and not has_unfinished_itasks:
                # We need to begin with an unfinished cycle point.
                continue
            points.append(point)

        if not points:
            return

        # Get the earliest point with unfinished tasks.
        runahead_base_point = min(points)

        # Get all cycling points possible after the runahead base point.
        if (self._prev_runahead_base_point is not None and 
                runahead_base_point == self._prev_runahead_base_point):
            # Cache for speed.
            sequence_points = self._prev_runahead_sequence_points
        else:
            sequence_points = []
            for sequence in self.config.sequences:
                point = runahead_base_point
                for i in range(limit):
                    point = sequence.get_next_point(point)
                    if point is None:
                        break
                    sequence_points.append(point)
            sequence_points = set(sequence_points)
            self._prev_runahead_sequence_points = sequence_points
            self._prev_runahead_base_point = runahead_base_point

        points = set(points).union(sequence_points)

        if self.custom_runahead_limit is None:
            # Calculate which tasks to release based on a maximum number of
            # active cycle points (active meaning non-finished tasks).
            latest_allowed_point = sorted(points)[:limit][-1]
            if self.minimum_runahead_limit is not None:
                latest_allowed_point = max([
                    latest_allowed_point,
                    runahead_base_point + self.minimum_runahead_limit
                ])
        else:
            # Calculate which tasks to release based on a maximum duration
            # measured from the oldest non-finished task.
            latest_allowed_point = (
                runahead_base_point + self.custom_runahead_limit)
        
        for point, itask_id_map in self.runahead_pool.items():
            if point <= latest_allowed_point:
                for itask in itask_id_map.values():
                    self.release_runahead_task(itask)
                    
    def release_runahead_task(self, itask):
        """Release itask to the appropriate queue in the active pool."""
        queue = self.myq[itask.name]
        if queue not in self.queues:
            self.queues[queue] = {}
        self.queues[queue][itask.id] = itask
        self.pool.setdefault(itask.c_time, {})
        self.pool[itask.c_time][itask.id] = itask
        self.pool_changed = True
        flags.pflag = True
        itask.log('DEBUG', "released to the task pool" )
        del self.runahead_pool[itask.c_time][itask.id]
        if not self.runahead_pool[itask.c_time]:
            del self.runahead_pool[itask.c_time]
        self.rhpool_changed = True
        try:
            self.pyro.connect( itask.message_queue, itask.id )
        except Exception, x:
            if flags.debug:
                raise
            print >> sys.stderr, x
            self.log.warning(
                '%s cannot be added (use --debug and see stderr)' % itask.id)
            return False


    def remove( self, itask, reason=None ):
        try:
            del self.runahead_pool[itask.c_time][itask.id]
        except KeyError:
            pass
        else:
            if not self.runahead_pool[itask.c_time]:
                del self.runahead_pool[itask.c_time]
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
        del self.pool[itask.c_time][itask.id]
        if not self.pool[itask.c_time]:
            del self.pool[itask.c_time]
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
                self.rhpool_list = []
                for itask_id_maps in self.runahead_pool.values():
                    self.rhpool_list.extend(itask_id_maps.values())

            return self.rhpool_list + self.pool_list
        else:
            return self.pool_list

    def get_tasks_by_point( self, all=False ):
        """Return a map of task proxies by cycle point."""
        point_itasks = {}
        for point, itask_id_map in self.pool.items():
            point_itasks[point] = itask_id_map.values()

        if not all:
            return point_itasks
        
        for point, itask_id_map in self.runahead_pool.items():
            point_itasks.setdefault(point, [])
            point_itasks[point].extend(itask_id_map.values())
        return point_itasks

    def id_exists( self, id ):
        """Check if task id is in the runahead_pool or pool"""
        for point, itask_ids in self.runahead_pool.items():
            if id in itask_ids:
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
        if not self.stop_point:
            return False
        for pct in set(itask.prerequisites.get_target_tags()):
            if pct > self.stop_point:
                return True
        return False

    def set_runahead( self, interval=None ):
        if isinstance(interval, int) or isinstance(interval, basestring):
            # The unit is assumed to be hours (backwards compatibility).
            interval = str(interval)
            interval_cls = get_interval_cls()
            if interval_cls.TYPE == ISO8601_CYCLING_TYPE:
                interval = get_interval("PT%sH" % interval)
            else:
                interval = get_interval(interval)
        if interval is None:
            # No limit
            self.log.warning( "setting NO runahead limit" )
            self.custom_runahead_limit = None
        else:
            self.log.info( "setting runahead limit to " + str(interval) )
            self.custom_runahead_limit = interval
        self.release_runahead_tasks()


    def get_min_ctime( self ):
        """Return the minimum cycle currently in the pool."""
        cycles = self.pool.keys()
        minc = None
        if cycles:
            minc = min(cycles)
        return minc


    def get_max_ctime( self ):
        """Return the maximum cycle currently in the pool."""
        cycles = self.pool.keys()
        maxc = None
        if cycles:
            maxc = max(cycles)
        return maxc


    def reconfigure( self, config, stop_point ):

        self.reconfiguring = True

        self.custom_runahead_limit = config.get_custom_runahead_limit()
        self.minimum_runahead_limit = config.get_minimum_runahead_limit()
        self.max_num_active_cycle_points = (
            config.get_max_num_active_cycle_points())
        self.config = config
        self.stop_point = stop_point  # TODO: Any point in using set_stop_point?

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
            if name not in self.task_name_list:
                self.orphans.append(name)
        # adjust the new suite config to handle the orphans
        config.adopt_orphans( self.orphans )
        

    def reload_taskdefs( self ):
        found = False
        for itask in self.get_tasks(all=True):
            if itask.state.is_currently('submitted','running'):
                # do not reload active tasks as it would be possible to
                # get a task proxy incompatible with the running task
                if itask.reconfigure_me:
                    found = True
                continue
            if itask.reconfigure_me:
                itask.reconfigure_me = False
                if itask.name in self.orphans:
                    # orphaned task
                    if itask.state.is_currently('waiting', 'queued', 'submit-retrying', 'retrying'):
                        # if not started running yet, remove it.
                        self.remove( itask, '(task orphaned by suite reload)' )
                    else:
                        # set spawned already so it won't carry on into the future
                        itask.state.set_spawned()
                        self.log.warning( 'orphaned task will not continue: ' + itask.id  )
                else:
                    self.log.info( 'RELOADING TASK DEFINITION FOR ' + itask.id  )
                    new_task = self.get_task_proxy( itask.name, itask.tag, itask.state.get_status(), None, itask.startup, submit_num=self.db.get_task_current_submit_num(itask.name, itask.tag), exists=self.db.get_task_state_exists(itask.name, itask.tag) )
                    # set reloaded task's spawn status
                    if itask.state.has_spawned():
                        new_task.state.set_spawned()
                    else:
                        new_task.state.set_unspawned()
                    # succeeded tasks need their outputs set completed:
                    if itask.state.is_currently('succeeded'):
                        new_task.reset_state_succeeded(manual=False)

                    # carry some task proxy state over to the new instance
                    new_task.summary = itask.summary
                    new_task.started_time = itask.started_time
                    new_task.submitted_time = itask.submitted_time
                    new_task.succeeded_time = itask.succeeded_time
                    new_task.etc = itask.etc

                    # if currently retrying, retain the old retry delay
                    # list, to avoid extra retries (the next instance
                    # of the task will still be as newly configured)
                    if itask.state.is_currently( 'retrying' ):
                        new_task.retry_delay = itask.retry_delay
                        new_task.retry_delays = itask.retry_delays
                        new_task.retry_delay_timer_timeout = (
                            itask.retry_delay_timer_timeout)
                    elif itask.state.is_currently( 'submit-retrying' ):
                        new_task.sub_retry_delay = itask.sub_retry_delay
                        new_task.sub_retry_delays = itask.sub_retry_delays
                        new_task.sub_retry_delays_orig = itask.sub_retry_delays_orig
                        new_task.sub_retry_delay_timer_timeout = (
                            itask.sub_retry_delay_timer_timeout)

                    new_task.try_number = itask.try_number
                    new_task.sub_try_number = itask.sub_try_number
                    new_task.submit_num = itask.submit_num


                    self.remove( itask, '(suite definition reload)' )
                    self.add_to_runahead_pool( new_task )

        self.reconfiguring = found

    def set_stop_point( self, stop_point ):
        """Set the global suite stop point."""
        self.stop_point = stop_point
        for itask in self.get_tasks():
            # check cycle stop or hold conditions
            if (self.stop_point and itask.c_time > self.stop_point and
                    itask.state.is_currently('waiting', 'queued')):
                itask.log( 'WARNING',
                           "not running (beyond suite stop cycle) " +
                           str(self.stop_point) )
                itask.reset_state_held()


    def no_active_tasks( self ):
        for itask in self.get_tasks():
            if itask.state.is_currently('running', 'submitted'):
                return False
        return True


    def poll_tasks( self,ids ):
        for itask in self.get_tasks():
            if itask.id in ids:
                # (state check done in task module)
                itask.poll()


    def kill_all_tasks( self ):
        for itask in self.get_tasks():
            if itask.state.is_currently( 'submitted', 'running' ):
                itask.kill()


    def kill_tasks( self,ids ):
        for itask in self.get_tasks():
            if itask.id in ids:
                # (state check done in task module)
                itask.kill()


    def hold_tasks( self, ids ):
        for itask in self.get_tasks(all=True):
            if itask.id in ids:
                if itask.state.is_currently('waiting', 'queued', 'submit-retrying', 'retrying' ):
                    itask.reset_state_held()


    def release_tasks( self,ids ):
        for itask in self.get_tasks(all=True):
            if itask.id in ids and itask.state.is_currently('held'):
                itask.reset_state_waiting()


    def hold_all_tasks( self ):
        self.log.info( "Holding all waiting or queued tasks now")
        for itask in self.get_tasks(all=True):
            if itask.state.is_currently('queued','waiting','submit-retrying', 'retrying'):
                itask.reset_state_held()


    def release_all_tasks( self ):
        # TODO ISO - check that we're not still holding tasks beyond suite
        # stop time (no point as finite-range tasks now disappear beyond
        # their stop time).
        for itask in self.get_tasks(all=True):
            if itask.state.is_currently('held'):
                #if self.stop_point and itask.c_time > self.stop_point:
                #    # this task has passed the suite stop time
                #    itask.log( 'NORMAL', "Not releasing (beyond suite stop cycle) " + str(self.stop_point) )
                #elif itask.stop_c_time and itask.c_time > itask.stop_c_time:
                #    # this task has passed its own stop time
                #    itask.log( 'NORMAL', "Not releasing (beyond task stop cycle) " + str(itask.stop_c_time) )
                #else:
                # release this task
                itask.reset_state_waiting()

        # TODO - write a separate method for cancelling a stop time:
        #if self.stop_point:
        #    self.log.warning( "UNSTOP: unsetting suite stop time")
        #    self.stop_point = None


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
        # TODO - THIS SHOULD BE IN task.py?
        if itask.state.has_spawned():
            return None
        itask.state.set_spawned()
        itask.log( 'DEBUG', 'forced spawning')
        new_task = itask.spawn( 'waiting' )
        if new_task and self.add_to_runahead_pool( new_task ):
            return new_task
        else:
            return None


    def spawn_tasks( self ):
        for itask in self.get_tasks():
            if itask.ready_to_spawn():
                self.force_spawn( itask )


    def remove_spent_tasks( self ):
        """Remove tasks no longer needed to satisfy others' prerequisites."""
        self.remove_suiciding_tasks()
        self.remove_spent_cycling_tasks()


    def remove_suiciding_tasks( self ):
        """Remove any tasks that have suicide-triggered."""
        for itask in self.get_tasks():
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    if itask.state.is_currently('ready', 'submitted', 'running'):
                        itask.log( 'WARNING', 'suiciding while active' )
                    else:
                        itask.log( 'NORMAL', 'suiciding' )
                    self.force_spawn( itask )
                    self.remove( itask, 'suicide' )


    def _get_earliest_unsatisfied_cycle_point( self ):
        cutoff = None
        for itask in self.get_tasks(all=True):
            # this has to consider tasks in the runahead pool too, e.g.
            # ones that have just spawned and not been released yet.
            if itask.state.is_currently('waiting', 'held' ):
                if cutoff is None or itask.c_time < cutoff:
                    cutoff = itask.c_time
            elif not itask.has_spawned():
                # (e.g. 'ready')
                nxt = itask.next_tag()
                if nxt is not None and ( cutoff is None or nxt < cutoff ):
                    cutoff = nxt
        return cutoff

    def remove_spent_cycling_tasks( self ):
        """
        Remove cycling tasks no longer needed to satisfy others' prerequisites.
        Each task proxy knows its "cleanup cutoff" from the graph. For example:
          graph = 'foo[T-6]=>bar \n foo[T-12]=>baz'
        implies foo's cutoff is T+12: if foo has succeeded and spawned,
        it can be removed if no unsatisfied task proxy exists with
        T<=T+12. Note this only uses information about the cycle point of
        downstream dependents - if we used specific IDs instead spent
        tasks could be identified and removed even earlier).
        """

        # first find the cycle point of the earliest unsatisfied task
        cutoff = self._get_earliest_unsatisfied_cycle_point()

        if not cutoff:
            return

        # now check each succeeded task against the cutoff
        spent = []
        for itask in self.get_tasks():
            if not itask.state.is_currently('succeeded') or \
                    not itask.state.has_spawned() or \
                    itask.cleanup_cutoff is None:
                continue
            if cutoff > itask.cleanup_cutoff:
                spent.append(itask)
        for itask in spent:
            self.remove( itask )


    def reset_task_states( self, ids, state ):
        # we only allow resetting to a subset of available task states
        if state not in [ 'ready', 'waiting', 'succeeded', 'failed', 'held', 'spawn' ]:
            raise SchedulerError, 'Illegal reset state: ' + state

        tasks = []
        for itask in self.get_tasks():
            if itask.id in ids:
                tasks.append( itask )

        for itask in tasks:
            if itask.state.is_currently( 'ready' ):
                # Currently can't reset a 'ready' task in the job submission thread!
                self.log.warning( "A 'ready' task cannot be reset: " + itask.id )
            itask.log( "NORMAL", "resetting to " + state + " state" )
            if state == 'ready':
                itask.reset_state_ready()
            elif state == 'waiting':
                itask.reset_state_waiting()
            elif state == 'succeeded':
                itask.reset_state_succeeded()
            elif state == 'failed':
                itask.reset_state_failed()
            elif state == 'held':
                itask.reset_state_held()
            elif state == 'spawn':
                self.force_spawn(itask)


    def remove_entire_cycle( self, tag, spawn ):
        for itask in self.get_tasks():
            if itask.tag == tag:
                if spawn:
                    self.force_spawn( itask )
                self.remove( itask, 'by request' )


    def remove_tasks( self, ids, spawn ):
        for itask in self.get_tasks():
            if itask.id in ids:
                if spawn:
                    self.force_spawn( itask )
                self.remove( itask, 'by request' )


    def trigger_tasks( self, ids ):
        for itask in self.get_tasks():
            if itask.id in ids:
                itask.manual_trigger = True
                itask.reset_state_ready()


    def check_task_timers( self ):
        for itask in self.get_tasks():
            itask.check_timers()


    def check_stop( self ):
        stop = True

        i_cyc = False
        i_fut = False
        for itask in self.get_tasks( all=True ):
            i_cyc = True
            # don't stop if a cycling task has not passed the stop cycle
            if self.stop_point:
                if itask.c_time <= self.stop_point:
                    if itask.state.is_currently('succeeded') and itask.has_spawned():
                        # ignore spawned succeeded tasks - their successors matter
                        pass
                    elif itask.id in self.held_future_tasks:
                        # unless held because a future trigger reaches beyond the stop cycle
                        i_fut = True
                        pass
                    else:
                        stop = False
                        break
            else:
                # don't stop if there are cycling tasks and no stop cycle set
                stop = False
                break
        if stop:
            msg = "Stopping: "
            if i_fut:
                msg += "\n  + all future-triggered tasks have run as far as possible toward " + str(self.stop_point)
            if i_cyc:
                msg += "\n  + all tasks have spawned past the final cycle " + str(self.stop_point)
            print msg
            self.log.info( msg )

        return stop


    def sim_time_check( self ):
        sim_task_succeeded = False
        for itask in self.get_tasks():
            if itask.state.is_currently('running'):
                # set sim-mode tasks to "succeeded" after their alotted run time
                if itask.sim_time_check():
                    sim_task_succeeded = True
        return sim_task_succeeded


    def shutdown( self ):
        if not self.no_active_tasks():
            self.log.warning( "some active tasks will be orphaned" )
        self.worker.quit = True # (should be done already)
        self.worker.join()
        self.pyro.disconnect( self.wireless )
        for itask in self.get_tasks():
            if itask.message_queue:
                self.pyro.disconnect( itask.message_queue )


    def waiting_tasks_ready( self ):
        # waiting tasks can become ready for internal reasons:
        # namely clock-triggers or retry-delay timers
        result = False
        for itask in self.get_tasks():
            if itask.ready_to_run():
                result = True
                break
        return result


    def add_prereq_to_task( self, id, msg ):
        for itask in self.get_tasks():
            if itask.id == id:
                break
        else:
            raise TaskNotFoundError, "Task not present in suite: " + id
        pp = plain_prerequisites( id )
        pp.add( msg )
        itask.prerequisites.add_requisites(pp)


    def has_stop_task_succeeded( self, id ):
        res = False
        name, tag = TaskID.split(id)
        for itask in self.get_tasks():
            iname, itag = TaskID.split(itask.id)
            # TODO ISO - check the following works
            if itask.name == name and get_point(itag) == get_point(tag):
                if itask.state.is_currently('succeeded'):
                    self.log.info( "Stop task " + id + " finished" )
                    res = True
                break
        return res


    def ping_task( self, id ):
        found = False
        running = False
        for itask in self.get_tasks():
            if itask.id == id:
                found = True
                if itask.state.is_currently('running'):
                    running = True
                break
        if not found:
            return False, "task not found"
        elif not running:
            return False, "task not running"
        else:
            return True, " running"


    def get_task_requisites( self, ids ):
        info = {}
        found = False
        for itask in self.get_tasks():
            id = itask.id
            if id in ids:
                found = True
                extra_info = {}
                # extra info for clocktriggered tasks
                try:
                    extra_info[ 'Delayed start time reached' ] = itask.start_time_reached()
                    extra_info[ 'Triggers at' ] = 'T+' + str(itask.real_time_delay) + ' hours'
                except AttributeError:
                    # not a clocktriggered task
                    pass

                info[ id ] = [ itask.prerequisites.dump(), itask.outputs.dump(), extra_info ]
        if not found:
            self.log.warning( 'task state info request: task(s) not found' )
        return info


    def purge_tree( self, id, stop ):
        # Remove an entire dependancy tree rooted on the target task,
        # through to the given stop time (inclusive). In general this
        # involves tasks that do not even exist yet within the pool.

        # Method: trigger the target task *virtually* (i.e. without
        # running the real task) by: setting it to the succeeded state,
        # setting all of its outputs completed, and forcing it to spawn.
        # (this is equivalent to instantaneous successful completion as
        # far as cylc is concerned). Then enter the normal dependency
        # negotation process to trace the downstream effects of this,
        # also triggering subsequent tasks virtually. Each time a task
        # triggers mark it as a dependency of the target task for later
        # deletion (but not immmediate deletion because other downstream
        # tasks may still trigger off its outputs).  Downstream tasks
        # (freshly spawned or not) are not triggered if they have passed
        # the stop time, and the process is stopped is soon as a
        # dependency negotation round results in no new tasks
        # triggering.

        # Finally, reset the prerequisites of all tasks spawned during
        # the purge to unsatisfied, since they may have been satisfied
        # by the purged tasks in the "virtual" dependency negotiations.
        # TODO - THINK ABOUT WHETHER THIS CAN APPLY TO TASKS THAT
        # ALREADY EXISTED PRE-PURGE, NOT ONLY THE JUST-SPAWNED ONES. If
        # so we should explicitly record the tasks that get satisfied
        # during the purge.


        # Purge is an infrequently used power tool, so print
        # comprehensive information on what it does to stdout.
        print
        print "PURGE ALGORITHM RESULTS:"

        die = []
        spawn = []

        print 'ROOT TASK:'
        for itask in self.get_tasks(all=True):
            # Find the target task
            if itask.id == id:
                # set it succeeded
                print '  Setting', itask.id, 'succeeded'
                itask.reset_state_succeeded(manual=False)
                # force it to spawn
                print '  Spawning', itask.id
                foo = self.force_spawn( itask )
                if foo:
                    spawn.append( foo )
                # mark it for later removal
                print '  Marking', itask.id, 'for deletion'
                die.append( itask )
                break

        print 'VIRTUAL TRIGGERING STOPPING AT', stop
        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.match_dependencies()
            something_triggered = False
            for itask in sorted(self.get_tasks(all=True), key=lambda t: t.id):
                if itask.tag > stop:
                    continue
                if itask.ready_to_run():
                    something_triggered = True
                    print '  Triggering', itask.id
                    itask.reset_state_succeeded(manual=False)
                    print '  Spawning', itask.id
                    foo = self.force_spawn( itask )
                    if foo:
                        spawn.append( foo )
                    print '  Marking', itask.id, 'for deletion'
                    # remove these later (their outputs may still be needed)
                    die.append( itask )
                elif itask.suicide_prerequisites.count() > 0:
                    if itask.suicide_prerequisites.all_satisfied():
                        print '  Spawning virtually activated suicide task', itask.id
                        self.force_spawn( itask )
                        # remove these now (not setting succeeded; outputs not needed)
                        print '  Suiciding', itask.id, 'now'
                        self.remove( itask, 'purge' )
            self.release_runahead_tasks()
        # reset any prerequisites "virtually" satisfied during the purge
        print 'RESETTING spawned tasks to unsatisified:'
        for itask in spawn:
            print '  ', itask.id
            itask.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        print 'REMOVING PURGED TASKS:'
        for itask in die:
            print '  ', itask.id
            self.remove( itask, 'purge' )

        print 'PURGE DONE'

