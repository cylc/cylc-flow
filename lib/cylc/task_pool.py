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
"""Manage the task pool of a suite.

All new task proxies (including spawned ones) are added first to the runahead
pool, which does not participate in dependency matching and is not visible in
the GUI. Tasks are then released to the task pool if not beyond the current
runahead limit.

check_auto_shutdown() and remove_spent_tasks() have to consider tasks in the
runahead pool too.

TODO - spawn-on-submit means a only one waiting instance of each task exists,
in the pool, so if a new stop cycle is set we just need to check waiting pool
tasks against the new stop cycle.

restart: runahead tasks are all in the 'waiting' state and will be reloaded
as such, on restart, into the runahead pool.

"""

import sys
from cylc.task_state import task_state
from cylc.broker import broker
import cylc.flags
from Pyro.errors import NamingError
from logging import WARNING, DEBUG, INFO

import cylc.rundb
from cylc.cycling.loader import (
    get_interval, get_interval_cls, ISO8601_CYCLING_TYPE)
from cylc.CylcError import SchedulerError, TaskNotFoundError
from cylc.prerequisites.plain_prerequisites import plain_prerequisites
from cylc.broadcast import broadcast


class TaskPool(object):
    """Task pool of a suite."""

    def __init__(
            self, suite, db, view_db, stop_point, config, pyro, log, run_mode):
        self.pyro = pyro
        self.run_mode = run_mode
        self.log = log
        self.qconfig = config.cfg['scheduling']['queues']
        self.stop_point = stop_point
        self.reconfiguring = False
        self.db = db
        self.view_db = view_db

        self.custom_runahead_limit = config.get_custom_runahead_limit()
        self.max_future_offset = None
        self._prev_runahead_base_point = None
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

        self.is_held = False

        self.held_future_tasks = []

        self.wireless = broadcast(config.get_linearized_ancestors())
        self.pyro.connect(self.wireless, 'broadcast_receiver')

        self.broker = broker()

        self.orphans = []
        self.task_name_list = config.get_task_name_list()

    def assign_queues(self):
        """self.myq[taskname] = qfoo"""
        self.myq = {}
        for queue in self.qconfig:
            for taskname in self.qconfig[queue]['members']:
                self.myq[taskname] = queue

    def add_to_runahead_pool(self, itask):
        """Add a new task to the runahead pool if possible.

        Tasks whose recurrences allow them to spawn beyond the suite
        stop point are added to the pool in the held state, ready to be
        released if the suite stop point is changed.

        """

        # do not add if a task with the same ID already exists
        # e.g. an inserted task caught up with an existing one
        if self.id_exists(itask.identity):
            self.log.warning(
                itask.identity +
                ' cannot be added to pool: task ID already exists')
            del itask
            return False

        # do not add if an inserted task is beyond its own stop point
        # (note this is not the same as recurrence bounds)
        if itask.stop_point and itask.point > itask.stop_point:
            self.log.info(
                itask.identity + ' not adding to pool: beyond task stop cycle')
            del itask
            return False

        # add in held state if beyond the suite stop point

        if self.stop_point and itask.point > self.stop_point:
            itask.log(
                INFO,
                "holding (beyond suite stop point) " + str(self.stop_point))
            itask.reset_state_held()

        # TODO ISO - restore this functionality
        #elif self.hold_time and itask.point > self.hold_time:
        #    itask.log(INFO, "holding (beyond suite hold point) " +
        #    str(self.hold_time))
        #    itask.reset_state_held()

        # add in held state if a future trigger goes beyond the suite stop
        # point (note this only applies to tasks below the suite stop point
        # themselves)
        elif self.task_has_future_trigger_overrun(itask):
            itask.log(INFO, "holding (future trigger beyond stop point)")
            self.held_future_tasks.append(itask.identity)
            itask.reset_state_held()
        elif self.is_held:
            itask.reset_state_held()

        # add to the runahead pool
        self.runahead_pool.setdefault(itask.point, {})
        self.runahead_pool[itask.point][itask.identity] = itask
        self.rhpool_changed = True
        return True

    def release_runahead_tasks(self):
        """Compute runahead base

        The oldest task not succeeded or failed (excludes finished and includes
        runahead-limited tasks so a low limit cannot stall the suite).

        """

        if not self.runahead_pool:
            return

        limit = self.max_num_active_cycle_points

        points = []
        for point, itasks in sorted(
                self.get_tasks_by_point(all_tasks=True).items()):
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
                for _ in range(limit):
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
            if self.max_future_offset is not None:
                # For the first N points, release their future trigger tasks.
                latest_allowed_point += self.max_future_offset
        else:
            # Calculate which tasks to release based on a maximum duration
            # measured from the oldest non-finished task.
            latest_allowed_point = (
                runahead_base_point + self.custom_runahead_limit)

            if (self._prev_runahead_base_point is None or
                    self._prev_runahead_base_point != runahead_base_point):
                if self.custom_runahead_limit < self.max_future_offset:
                    self.log.warning(
                        'custom runahead limit of %s is less than ' +
                        'future triggering offset %s: suite may stall.' % (
                            self.custom_runahead_limit,
                            self.max_future_offset
                        )
                    )
            self._prev_runahead_base_point = runahead_base_point

        for point, itask_id_map in self.runahead_pool.items():
            if point <= latest_allowed_point:
                for itask in itask_id_map.values():
                    self.release_runahead_task(itask)

    def release_runahead_task(self, itask):
        """Release itask to the appropriate queue in the active pool."""
        queue = self.myq[itask.tdef.name]
        if queue not in self.queues:
            self.queues[queue] = {}
        self.queues[queue][itask.identity] = itask
        self.pool.setdefault(itask.point, {})
        self.pool[itask.point][itask.identity] = itask
        self.pool_changed = True
        cylc.flags.pflag = True
        itask.log(DEBUG, "released to the task pool")
        del self.runahead_pool[itask.point][itask.identity]
        if not self.runahead_pool[itask.point]:
            del self.runahead_pool[itask.point]
        self.rhpool_changed = True
        try:
            self.pyro.connect(itask.message_queue, itask.identity)
        except Exception, exc:
            if cylc.flags.debug:
                raise
            print >> sys.stderr, exc
            self.log.warning(
                '%s cannot be added (use --debug and see stderr)' %
                itask.identity)
            return False
        if itask.tdef.max_future_prereq_offset is not None:
            self.set_max_future_offset()

    def remove(self, itask, reason=None):
        """Remove a task proxy from the pool."""
        try:
            del self.runahead_pool[itask.point][itask.identity]
        except KeyError:
            pass
        else:
            if not self.runahead_pool[itask.point]:
                del self.runahead_pool[itask.point]
            self.rhpool_changed = True
            return

        try:
            self.pyro.disconnect(itask.message_queue)
        except NamingError, exc:
            print >> sys.stderr, exc
            self.log.critical(
                itask.identity + ' cannot be removed (task not found)')
            return
        except Exception, exc:
            print >> sys.stderr, exc
            self.log.critical(
                itask.identity + ' cannot be removed (unknown error)')
            return
        # remove from queue
        if itask.tdef.name in self.myq:  # A reload can remove a task
            del self.queues[self.myq[itask.tdef.name]][itask.identity]
        del self.pool[itask.point][itask.identity]
        if not self.pool[itask.point]:
            del self.pool[itask.point]
        self.pool_changed = True
        msg = "task proxy removed"
        if reason:
            msg += " (" + reason + ")"
        itask.log(DEBUG, msg)
        if itask.tdef.max_future_prereq_offset is not None:
            self.set_max_future_offset()
        del itask

    def get_tasks(self, all_tasks=False):
        """ Return the current list of task proxies."""

        # Regenerate the task lists on demand only if they have changed
        # (only necessary if computing the list takes significant time?)

        # May not be necessary at all once we centralize all pool ops?

        if self.pool_changed:
            self.pool_changed = False
            self.pool_list = []
            for queue in self.queues:
                for itask in self.queues[queue].values():
                    self.pool_list.append(itask)

        if all_tasks:
            if self.rhpool_changed:
                self.rhpool_changed = False
                self.rhpool_list = []
                for itask_id_maps in self.runahead_pool.values():
                    self.rhpool_list.extend(itask_id_maps.values())

            return self.rhpool_list + self.pool_list
        else:
            return self.pool_list

    def get_tasks_by_point(self, all_tasks=False):
        """Return a map of task proxies by cycle point."""
        point_itasks = {}
        for point, itask_id_map in self.pool.items():
            point_itasks[point] = itask_id_map.values()

        if not all_tasks:
            return point_itasks

        for point, itask_id_map in self.runahead_pool.items():
            point_itasks.setdefault(point, [])
            point_itasks[point].extend(itask_id_map.values())
        return point_itasks

    def id_exists(self, id_):
        """Check if task id is in the runahead_pool or pool"""
        for itask_ids in self.runahead_pool.values():
            if id_ in itask_ids:
                return True
        for queue in self.queues:
            if id_ in self.queues[queue]:
                return True
        return False

    def process(self):
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
            if not itask.state.is_currently('queued'):
                # only need to check that unqueued tasks are ready
                if itask.manual_trigger or itask.ready_to_run():
                    # queue the task
                    itask.set_status('queued')
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
                    if itask.state.is_currently(
                            'ready', 'submitted', 'running'):
                        n_active += 1
                n_release = n_limit - n_active

            # 2.2) release queued tasks if not limited or if manually forced
            for itask in tasks:
                if not itask.state.is_currently('queued'):
                    # (Note this excludes tasks remaining 'ready' because job
                    # submission has been stopped by use of 'cylc shutdown').
                    continue
                if itask.manual_trigger or not n_limit or n_release > 0:
                    # manual release, or no limit, or not currently limited
                    n_release -= 1
                    readytogo.append(itask)
                    if itask.manual_trigger:
                        itask.reset_manual_trigger()
                # else leaved queued

        self.log.debug('%d task(s) de-queued' % len(readytogo))

        for itask in readytogo:
            itask.submit(overrides=self.wireless.get(itask.identity))

        return readytogo

    def task_has_future_trigger_overrun(self, itask):
        """Check for future triggers extending beyond the final cycle."""
        if not self.stop_point:
            return False
        for pct in set(itask.prerequisites.get_target_points()):
            if pct > self.stop_point:
                return True
        return False

    def set_runahead(self, interval=None):
        """Set the runahead."""
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
            self.log.warning("setting NO custom runahead limit")
            self.custom_runahead_limit = None
        else:
            self.log.info("setting custom runahead limit to %s" % interval)
            self.custom_runahead_limit = interval
        self.release_runahead_tasks()

    def get_min_point(self):
        """Return the minimum cycle point currently in the pool."""
        cycles = self.pool.keys()
        minc = None
        if cycles:
            minc = min(cycles)
        return minc

    def get_max_point(self):
        """Return the maximum cycle point currently in the pool."""
        cycles = self.pool.keys()
        maxc = None
        if cycles:
            maxc = max(cycles)
        return maxc

    def set_max_future_offset(self):
        """Calculate the latest required future trigger offset."""
        max_offset = None
        for itask in self.get_tasks():
            if (itask.tdef.max_future_prereq_offset is not None and
                    (max_offset is None or
                     itask.tdef.max_future_prereq_offset > max_offset)):
                max_offset = itask.tdef.max_future_prereq_offset
        self.max_future_offset = max_offset

    def reconfigure(self, config, stop_point):
        """Set the task pool to reload mode."""
        self.reconfiguring = True

        self.custom_runahead_limit = config.get_custom_runahead_limit()
        self.max_num_active_cycle_points = (
            config.get_max_num_active_cycle_points())
        self.config = config
        self.stop_point = stop_point

        # reassign live tasks from the old queues to the new.
        # self.queues[queue][id_] = task
        self.qconfig = config.cfg['scheduling']['queues']
        self.assign_queues()
        new_queues = {}
        for queue in self.queues:
            for id_, itask in self.queues[queue].items():
                if itask.tdef.name not in self.myq:
                    continue
                key = self.myq[itask.tdef.name]
                if key not in new_queues:
                    new_queues[key] = {}
                new_queues[key][id_] = itask
        self.queues = new_queues

        for itask in self.get_tasks(all_tasks=True):
            itask.reconfigure_me = True

        # find any old tasks that have been removed from the suite
        old_task_name_list = self.task_name_list
        self.task_name_list = config.get_task_name_list()
        for name in old_task_name_list:
            if name not in self.task_name_list:
                self.orphans.append(name)
        # adjust the new suite config to handle the orphans
        config.adopt_orphans(self.orphans)

    def reload_taskdefs(self):
        """Reload task definitions."""
        found = False
        for itask in self.get_tasks(all_tasks=True):
            if itask.state.is_currently('ready', 'submitted', 'running'):
                # do not reload active tasks as it would be possible to
                # get a task proxy incompatible with the running task
                if itask.reconfigure_me:
                    found = True
                continue
            if itask.reconfigure_me:
                itask.reconfigure_me = False
                if itask.tdef.name in self.orphans:
                    # orphaned task
                    if itask.state.is_currently(
                            'waiting', 'queued', 'submit-retrying',
                            'retrying'):
                        # if not started running yet, remove it.
                        self.remove(itask, '(task orphaned by suite reload)')
                    else:
                        # set spawned already so it won't carry on into the
                        # future
                        itask.state.set_spawned()
                        self.log.warning(
                            'orphaned task will not continue: ' +
                            itask.identity)
                else:
                    self.log.info(
                        'RELOADING TASK DEFINITION FOR ' + itask.identity)
                    new_task = self.config.get_task_proxy(
                        itask.tdef.name,
                        itask.point,
                        itask.state.get_status(),
                        stop_point=itask.stop_point,
                        submit_num=itask.submit_num,
                        is_reload=True
                    )
                    # set reloaded task's spawn status
                    if itask.state.has_spawned():
                        new_task.state.set_spawned()
                    else:
                        new_task.state.set_unspawned()
                    # succeeded tasks need their outputs set completed:
                    if itask.state.is_currently('succeeded'):
                        new_task.reset_state_succeeded(manual=False)

                    # carry some task proxy state over to the new instance
                    new_task.logfiles = itask.logfiles
                    new_task.summary = itask.summary
                    new_task.started_time = itask.started_time
                    new_task.submitted_time = itask.submitted_time
                    new_task.finished_time = itask.finished_time

                    # if currently retrying, retain the old retry delay
                    # list, to avoid extra retries (the next instance
                    # of the task will still be as newly configured)
                    if itask.state.is_currently('retrying'):
                        new_task.retry_delay = itask.retry_delay
                        new_task.retry_delays = itask.retry_delays
                        new_task.retry_delay_timer_timeout = (
                            itask.retry_delay_timer_timeout)
                    elif itask.state.is_currently('submit-retrying'):
                        new_task.sub_retry_delay = itask.sub_retry_delay
                        new_task.sub_retry_delays = itask.sub_retry_delays
                        new_task.sub_retry_delays_orig = (
                            itask.sub_retry_delays_orig)
                        new_task.sub_retry_delay_timer_timeout = (
                            itask.sub_retry_delay_timer_timeout)

                    new_task.try_number = itask.try_number
                    new_task.sub_try_number = itask.sub_try_number
                    new_task.submit_num = itask.submit_num
                    new_task.db_queue = itask.db_queue

                    self.remove(itask, '(suite definition reload)')
                    self.add_to_runahead_pool(new_task)

        self.reconfiguring = found

    def set_stop_point(self, stop_point):
        """Set the global suite stop point."""
        self.stop_point = stop_point
        for itask in self.get_tasks():
            # check cycle stop or hold conditions
            if (self.stop_point and itask.point > self.stop_point and
                    itask.state.is_currently('waiting', 'queued')):
                itask.log(WARNING,
                          "not running (beyond suite stop cycle) " +
                          str(self.stop_point))
                itask.reset_state_held()

    def no_active_tasks(self):
        for itask in self.get_tasks():
            if itask.state.is_currently('running', 'submitted'):
                return False
        return True

    def poll_tasks(self, ids):
        for itask in self.get_tasks():
            if itask.identity in ids:
                # (state check done in task module)
                itask.poll()

    def kill_active_tasks(self):
        for itask in self.get_tasks():
            if itask.state.is_currently('submitted', 'running'):
                itask.kill()

    def kill_tasks(self, ids):
        for itask in self.get_tasks():
            if itask.identity in ids:
                # (state check done in task module)
                itask.kill()

    def hold_tasks(self, ids):
        for itask in self.get_tasks(all_tasks=True):
            if itask.identity in ids:
                if itask.state.is_currently(
                        'waiting', 'queued', 'submit-retrying', 'retrying'):
                    itask.reset_state_held()

    def release_tasks(self, ids):
        for itask in self.get_tasks(all_tasks=True):
            if itask.identity in ids and itask.state.is_currently('held'):
                itask.reset_state_waiting()

    def hold_all_tasks(self):
        self.log.info("Holding all waiting or queued tasks now")
        self.is_held = True
        for itask in self.get_tasks(all_tasks=True):
            if itask.state.is_currently(
                    'queued', 'waiting', 'submit-retrying', 'retrying'):
                itask.reset_state_held()

    def release_all_tasks(self):
        self.is_held = False
        for itask in self.get_tasks(all_tasks=True):
            if itask.state.is_currently('held'):
                if self.stop_point and itask.point > self.stop_point:
                    # Don't release task: beyond suite stop point.
                    continue
                else:
                    # Release task.
                    itask.reset_state_waiting()

    def get_failed_tasks(self):
        failed = []
        for itask in self.get_tasks():
            if itask.state.is_currently('failed', 'submit-failed'):
                failed.append(itask)
        return failed

    def any_task_failed(self):
        for itask in self.get_tasks():
            if itask.state.is_currently('failed', 'submit-failed'):
                return True
        return False

    def match_dependencies(self):
        """Run time dependency negotiation.

        Tasks attempt to get their prerequisites satisfied by other tasks'
        outputs. BROKERED NEGOTIATION is O(n) in number of tasks.

        """

        self.broker.reset()

        self.broker.register(self.get_tasks())

        for itask in self.get_tasks():
            # try to satisfy itask if not already satisfied.
            if itask.not_fully_satisfied():
                self.broker.negotiate(itask)

    def process_queued_task_messages(self):
        """Save queued task messages to persistent storage."""
        state_recorders = []
        state_updaters = []
        event_recorders = []
        other = []

        for itask in self.get_tasks():
            itask.process_incoming_messages()
            # if incoming messages have resulted in new database operations
            # grab them
            for oper in itask.get_db_ops():
                if isinstance(oper, cylc.rundb.UpdateObject):
                    state_updaters += [oper]
                elif isinstance(oper, cylc.rundb.RecordStateObject):
                    state_recorders += [oper]
                elif isinstance(oper, cylc.rundb.RecordEventObject):
                    event_recorders += [oper]
                else:
                    other += [oper]

        # precedence is record states > update_states > record_events >
        # anything_else
        db_ops = state_recorders + state_updaters + event_recorders + other
        # compact the set of operations
        if len(db_ops) > 1:
            db_opers = [db_ops[0]]
            for i in range(1, len(db_ops)):
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
            for db_oper in self.wireless.get_db_ops():
                db_opers += [db_oper]

        for db_oper in db_opers:
            if self.db.c.is_alive():
                self.db.run_db_op(db_oper)
            elif self.db.c.exception:
                self.view_db.close()
                raise self.db.c.exception
            else:
                raise SchedulerError(
                    'An unexpected error occurred while writing to the ' +
                    'suite database')

        # we should filter down to only recording the utility relevent
        # entries in the viewable database following database refactoring
        for db_oper in db_opers:
            if self.view_db.c.is_alive():
                self.view_db.run_db_op(db_oper)
            elif self.view_db.c.exception:
                self.db.close()
                raise self.view_db.c.exception
            else:
                raise SchedulerError(
                    'An unexpected error occurred while writing to the ' +
                    'viewable database')

    def force_spawn(self, itask):
        """Spawn successor of itask."""
        if itask.state.has_spawned():
            return None
        itask.state.set_spawned()
        itask.log(DEBUG, 'forced spawning')
        new_task = itask.spawn('waiting')
        if new_task and self.add_to_runahead_pool(new_task):
            return new_task
        else:
            return None

    def spawn_tasks(self):
        """Spawn successors of tasks in pool."""
        for itask in self.get_tasks():
            if itask.ready_to_spawn():
                self.force_spawn(itask)

    def remove_suiciding_tasks(self):
        """Remove any tasks that have suicide-triggered."""
        for itask in self.get_tasks():
            if itask.suicide_prerequisites.count() != 0:
                if itask.suicide_prerequisites.all_satisfied():
                    if itask.state.is_currently(
                            'ready', 'submitted', 'running'):
                        itask.log(WARNING, 'suiciding while active')
                    else:
                        itask.log(INFO, 'suiciding')
                    self.force_spawn(itask)
                    self.remove(itask, 'suicide')

    def _get_earliest_unsatisfied_point(self):
        """Get earliest unsatisfied cycle point."""
        cutoff = None
        for itask in self.get_tasks(all_tasks=True):
            # this has to consider tasks in the runahead pool too, e.g.
            # ones that have just spawned and not been released yet.
            if itask.state.is_currently('waiting', 'held'):
                if cutoff is None or itask.point < cutoff:
                    cutoff = itask.point
            elif not itask.state.has_spawned():
                # (e.g. 'ready')
                nxt = itask.next_point()
                if nxt is not None and (cutoff is None or nxt < cutoff):
                    cutoff = nxt
        return cutoff

    def remove_spent_tasks(self):
        """Remove cycling tasks that are no longer needed.

        Remove cycling tasks that are no longer needed to satisfy others'
        prerequisites.  Each task proxy knows its "cleanup cutoff" from the
        graph. For example:
          graph = 'foo[T-6]=>bar \n foo[T-12]=>baz'
        implies foo's cutoff is T+12: if foo has succeeded and spawned,
        it can be removed if no unsatisfied task proxy exists with
        T<=T+12. Note this only uses information about the cycle point of
        downstream dependents - if we used specific IDs instead spent
        tasks could be identified and removed even earlier).

        """

        # first find the cycle point of the earliest unsatisfied task
        cutoff = self._get_earliest_unsatisfied_point()

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
            self.remove(itask)

    def reset_task_states(self, ids, state):
        """Reset task states.

        We only allow resetting to a subset of available task states

        """
        if state not in task_state.legal_for_reset:
            raise SchedulerError('Illegal reset state: ' + state)

        tasks = []
        for itask in self.get_tasks():
            if itask.identity in ids:
                tasks.append(itask)

        for itask in tasks:
            if itask.state.is_currently('ready'):
                # Currently can't reset a 'ready' task in the job submission
                # thread!
                self.log.warning(
                    "A 'ready' task cannot be reset: " + itask.identity)
            itask.log(INFO, "resetting to " + state + " state")
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

    def remove_entire_cycle(self, point, spawn):
        for itask in self.get_tasks():
            if itask.point == point:
                if spawn:
                    self.force_spawn(itask)
                self.remove(itask, 'by request')

    def remove_tasks(self, ids, spawn):
        for itask in self.get_tasks():
            if itask.identity in ids:
                if spawn:
                    self.force_spawn(itask)
                self.remove(itask, 'by request')

    def trigger_tasks(self, ids):
        for itask in self.get_tasks():
            if itask.identity in ids:
                itask.manual_trigger = True
                if not itask.state.is_currently('queued'):
                    itask.reset_state_ready()

    def check_task_timers(self):
        for itask in self.get_tasks():
            itask.check_timers()

    def check_auto_shutdown(self):
        """Check if we should do a normal automatic shutdown."""
        shutdown = True
        for itask in self.get_tasks(all_tasks=True):
            if self.stop_point is None:
                # Don't if any unsucceeded task exists.
                if not itask.state.is_currently('succeeded'):
                    shutdown = False
                    break
            elif (itask.point <= self.stop_point and
                    not itask.state.is_currently('succeeded')):
                # Don't if any unsucceeded task exists < stop point...
                if itask.identity not in self.held_future_tasks:
                    # ...unless it has a future trigger extending > stop point.
                    shutdown = False
                    break
        return shutdown

    def sim_time_check(self):
        sim_task_succeeded = False
        for itask in self.get_tasks():
            if itask.state.is_currently('running'):
                # set sim-mode tasks to "succeeded" after their alotted run
                # time
                if itask.sim_time_check():
                    sim_task_succeeded = True
        return sim_task_succeeded

    def shutdown(self):
        if not self.no_active_tasks():
            self.log.warning("some active tasks will be orphaned")
        self.pyro.disconnect(self.wireless)
        for itask in self.get_tasks():
            if itask.message_queue:
                self.pyro.disconnect(itask.message_queue)

    def waiting_tasks_ready(self):
        """Waiting tasks can become ready for internal reasons.

        Namely clock-triggers or retry-delay timers

        """
        result = False
        for itask in self.get_tasks():
            if itask.ready_to_run():
                result = True
                break
        return result

    def add_prereq_to_task(self, id_, msg):
        for itask in self.get_tasks():
            if itask.identity == id_:
                prereq = plain_prerequisites(id_)
                prereq.add(msg)
                itask.prerequisites.add_requisites(prereq)
                break
        else:
            raise TaskNotFoundError("Task not present in suite: " + id_)

    def task_succeeded(self, id_):
        res = False
        for itask in self.get_tasks():
            if itask.identity == id_ and itask.state.is_currently('succeeded'):
                res = True
                break
        return res

    def ping_task(self, id_):
        found = False
        running = False
        for itask in self.get_tasks():
            if itask.identity == id_:
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

    def get_task_requisites(self, ids):
        info = {}
        found = False
        for itask in self.get_tasks():
            id_ = itask.identity
            if id_ in ids:
                found = True
                extra_info = {}
                # extra info for clocktriggered tasks
                if itask.tdef.clocktrigger_offset is not None:
                    extra_info['Clock trigger time reached'] = (
                        itask.start_time_reached())
                    extra_info['Triggers at'] = itask.delayed_start_str

                info[id_] = [
                    itask.prerequisites.dump(),
                    itask.outputs.dump(),
                    extra_info,
                ]
        if not found:
            self.log.warning('task state info request: task(s) not found')
        return info

    def purge_tree(self, id_, stop):
        """Remove an entire dependency tree.

        Remove an entire dependency tree rooted on the target task,
        through to the given stop time (inclusive). In general this
        involves tasks that do not even exist yet within the pool.

        Method: trigger the target task *virtually* (i.e. without
        running the real task) by: setting it to the succeeded state,
        setting all of its outputs completed, and forcing it to spawn.
        (this is equivalent to instantaneous successful completion as
        far as cylc is concerned). Then enter the normal dependency
        negotation process to trace the downstream effects of this,
        also triggering subsequent tasks virtually. Each time a task
        triggers mark it as a dependency of the target task for later
        deletion (but not immmediate deletion because other downstream
        tasks may still trigger off its outputs).  Downstream tasks
        (freshly spawned or not) are not triggered if they have passed
        the stop time, and the process is stopped is soon as a
        dependency negotation round results in no new tasks
        triggering.

        Finally, reset the prerequisites of all tasks spawned during
        the purge to unsatisfied, since they may have been satisfied
        by the purged tasks in the "virtual" dependency negotiations.

        TODO - THINK ABOUT WHETHER THIS CAN APPLY TO TASKS THAT
        ALREADY EXISTED PRE-PURGE, NOT ONLY THE JUST-SPAWNED ONES. If
        so we should explicitly record the tasks that get satisfied
        during the purge.

        Purge is an infrequently used power tool, so print
        comprehensive information on what it does to stdout.

        """

        print
        print "PURGE ALGORITHM RESULTS:"

        die = []
        spawn = []

        print 'ROOT TASK:'
        for itask in self.get_tasks(all_tasks=True):
            # Find the target task
            if itask.identity == id_:
                # set it succeeded
                print '  Setting', itask.identity, 'succeeded'
                itask.reset_state_succeeded(manual=False)
                # force it to spawn
                print '  Spawning', itask.identity
                spawned = self.force_spawn(itask)
                if spawned:
                    spawn.append(spawned)
                # mark it for later removal
                print '  Marking', itask.identity, 'for deletion'
                die.append(itask)
                break

        print 'VIRTUAL TRIGGERING STOPPING AT', stop
        # trace out the tree of dependent tasks
        something_triggered = True
        while something_triggered:
            self.match_dependencies()
            something_triggered = False
            for itask in sorted(
                    self.get_tasks(all_tasks=True), key=lambda t: t.identity):
                if itask.point > stop:
                    continue
                if itask.ready_to_run():
                    something_triggered = True
                    print '  Triggering', itask.identity
                    itask.reset_state_succeeded(manual=False)
                    print '  Spawning', itask.identity
                    spawned = self.force_spawn(itask)
                    if spawned:
                        spawn.append(spawned)
                    print '  Marking', itask.identity, 'for deletion'
                    # remove these later (their outputs may still be needed)
                    die.append(itask)
                elif itask.suicide_prerequisites.count() > 0:
                    if itask.suicide_prerequisites.all_satisfied():
                        print (
                            '  Spawning virtually activated suicide task ' +
                            itask.identity)
                        self.force_spawn(itask)
                        # remove these now (not setting succeeded; outputs not
                        # needed)
                        print '  Suiciding', itask.identity, 'now'
                        self.remove(itask, 'purge')
            self.release_runahead_tasks()
        # reset any prerequisites "virtually" satisfied during the purge
        print 'RESETTING spawned tasks to unsatisified:'
        for itask in spawn:
            print '  ', itask.identity
            itask.prerequisites.set_all_unsatisfied()

        # finally, purge all tasks marked as depending on the target
        print 'REMOVING PURGED TASKS:'
        for itask in die:
            print '  ', itask.identity
            self.remove(itask, 'purge')

        print 'PURGE DONE'
