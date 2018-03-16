#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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

"""

from fnmatch import fnmatchcase
import pickle
from time import time
import traceback

from cylc.config import SuiteConfigError
from cylc.cycling.loader import get_point, standardise_point_string
import cylc.flags
from cylc.suite_logging import ERR, LOG
from cylc.task_action_timer import TaskActionTimer
from cylc.task_id import TaskID
from cylc.task_proxy import TaskProxy
from cylc.task_state import (
    TASK_STATUSES_ACTIVE, TASK_STATUSES_NOT_STALLED,
    TASK_STATUS_HELD, TASK_STATUS_WAITING, TASK_STATUS_EXPIRED,
    TASK_STATUS_QUEUED, TASK_STATUS_READY, TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_SUBMIT_RETRYING,
    TASK_STATUS_RUNNING, TASK_STATUS_SUCCEEDED, TASK_STATUS_FAILED,
    TASK_STATUS_RETRYING)
from cylc.wallclock import (
    get_current_time_string, get_time_string_from_unix_time)
from parsec.OrderedDict import OrderedDict


class TaskPool(object):
    """Task pool of a suite."""

    ERR_PREFIX_TASKID_MATCH = "No matching tasks found: "
    ERR_PREFIX_TASK_NOT_ON_SEQUENCE = "Invalid cycle point for task: "

    STOP_AUTO = 'AUTOMATIC'
    STOP_AUTO_ON_TASK_FAILURE = 'AUTOMATIC(ON-TASK-FAILURE)'
    STOP_REQUEST_CLEAN = 'REQUEST(CLEAN)'
    STOP_REQUEST_NOW = 'REQUEST(NOW)'
    STOP_REQUEST_NOW_NOW = 'REQUEST(NOW-NOW)'

    def __init__(self, config, stop_point, suite_db_mgr, task_events_mgr):
        self.config = config
        self.stop_point = stop_point
        self.suite_db_mgr = suite_db_mgr
        self.task_events_mgr = task_events_mgr

        self.do_reload = False
        self.custom_runahead_limit = self.config.get_custom_runahead_limit()
        self.max_future_offset = None
        self._prev_runahead_base_point = None
        self.max_num_active_cycle_points = (
            self.config.get_max_num_active_cycle_points())
        self._prev_runahead_sequence_points = None

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
        self.hold_point = None
        self.held_future_tasks = []

        self.orphans = []
        self.task_name_list = self.config.get_task_name_list()

    def assign_queues(self):
        """self.myq[taskname] = qfoo"""
        self.myq.clear()
        for queue, qconfig in self.config.cfg['scheduling']['queues'].items():
            self.myq.update((name, queue) for name in qconfig['members'])

    def insert_tasks(self, items, stop_point_str, no_check=False):
        """Insert tasks."""
        n_warnings = 0
        task_items = {}
        select_args = []
        for item in items:
            point_str, name_str = self._parse_task_item(item)[:2]
            if point_str is None:
                LOG.warning(
                    "%s: task ID for insert must contain cycle point" % (item))
                n_warnings += 1
                continue
            try:
                point_str = standardise_point_string(point_str)
            except ValueError as exc:
                LOG.warning(
                    self.ERR_PREFIX_TASKID_MATCH + ("%s (%s)" % (item, exc)))
                n_warnings += 1
                continue
            taskdefs = self.config.find_taskdefs(name_str)
            if not taskdefs:
                LOG.warning(self.ERR_PREFIX_TASKID_MATCH + item)
                n_warnings += 1
                continue
            for taskdef in taskdefs:
                task_items[(taskdef.name, point_str)] = taskdef
            select_args.append((name_str, point_str))
        if stop_point_str is None:
            stop_point = None
        else:
            try:
                stop_point = get_point(
                    standardise_point_string(stop_point_str))
            except ValueError as exc:
                LOG.warning("Invalid stop point: %s (%s)" % (
                    stop_point_str, exc))
                n_warnings += 1
                return n_warnings
        submit_nums = self.suite_db_mgr.pri_dao.select_submit_nums_for_insert(
            select_args)
        for key, taskdef in sorted(task_items.items()):
            # TODO - insertion of start-up tasks? (startup=False assumed here)

            # Check that the cycle point is on one of the tasks sequences.
            point = get_point(key[1])
            if not no_check:  # Check if cycle point is on the tasks sequence.
                for sequence in taskdef.sequences:
                    if sequence.is_on_sequence(point):
                        break
                else:
                    LOG.warning("%s%s, %s" % (
                        self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE, taskdef.name,
                        key[1]))
                    continue

            submit_num = submit_nums.get(key)
            itask = self.add_to_runahead_pool(TaskProxy(
                taskdef, point, stop_point=stop_point, submit_num=submit_num))
            if itask:
                LOG.info("inserted", itask=itask)
        return n_warnings

    def add_to_runahead_pool(self, itask, is_restart=False):
        """Add a new task to the runahead pool if possible.

        Tasks whose recurrences allow them to spawn beyond the suite
        stop point are added to the pool in the held state, ready to be
        released if the suite stop point is changed.

        """

        # do not add if a task with the same ID already exists
        # e.g. an inserted task caught up with an existing one
        if self.get_task_by_id(itask.identity) is not None:
            LOG.warning(
                '%s cannot be added to pool: task ID already exists' %
                itask.identity)
            return

        # do not add if an inserted task is beyond its own stop point
        # (note this is not the same as recurrence bounds)
        if itask.stop_point and itask.point > itask.stop_point:
            LOG.info(
                '%s not adding to pool: beyond task stop cycle' %
                itask.identity)
            return

        # add in held state if beyond the suite hold point
        if self.hold_point and itask.point > self.hold_point:
            LOG.info(
                "holding (beyond suite hold point) %s" % self.hold_point,
                itask=itask)
            itask.state.set_held()
        elif (itask.point <= self.stop_point and
                self.task_has_future_trigger_overrun(itask)):
            LOG.info("holding (future trigger beyond stop point)", itask=itask)
            self.held_future_tasks.append(itask.identity)
            itask.state.set_held()
        elif self.is_held and itask.state.status == TASK_STATUS_WAITING:
            # Hold newly-spawned tasks in a held suite (e.g. due to manual
            # triggering of a held task).
            itask.state.set_held()

        # add to the runahead pool
        self.runahead_pool.setdefault(itask.point, OrderedDict())
        self.runahead_pool[itask.point][itask.identity] = itask
        self.rhpool_changed = True

        if is_restart:
            return itask

        # store in persistent
        if itask.submit_num > 0:
            self.suite_db_mgr.put_update_task_states(itask, {
                "time_updated": get_current_time_string(),
                "status": itask.state.status})
        else:
            self.suite_db_mgr.put_insert_task_states(itask, {
                "time_created": get_current_time_string(),
                "time_updated": get_current_time_string(),
                "status": itask.state.status})
            if itask.state.outputs.has_custom_triggers():
                self.suite_db_mgr.put_insert_task_outputs(itask)
        return itask

    def release_runahead_tasks(self):
        """Release tasks from the runahead pool to the main pool.

        Return True if any tasks are released, else False.
        """
        released = False
        if not self.runahead_pool:
            return released

        # Any finished tasks can be released immediately (this can happen at
        # restart when all tasks are initially loaded into the runahead pool).
        for itask_id_maps in self.runahead_pool.copy().values():
            for itask in itask_id_maps.copy().values():
                if itask.state.status in [TASK_STATUS_FAILED,
                                          TASK_STATUS_SUCCEEDED,
                                          TASK_STATUS_EXPIRED]:
                    self.release_runahead_task(itask)
                    released = True

        limit = self.max_num_active_cycle_points

        points = []
        for point, itasks in sorted(
                self.get_tasks_by_point(incl_runahead=True).items()):
            has_unfinished_itasks = False
            for itask in itasks:
                if itask.state.status not in [TASK_STATUS_FAILED,
                                              TASK_STATUS_SUCCEEDED,
                                              TASK_STATUS_EXPIRED]:
                    has_unfinished_itasks = True
                    break
            if not points and not has_unfinished_itasks:
                # We need to begin with an unfinished cycle point.
                continue
            points.append(point)

        if not points:
            return False

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
                    LOG.warning(
                        ('custom runahead limit of %s is less than ' +
                         'future triggering offset %s: suite may stall.') % (
                            self.custom_runahead_limit,
                            self.max_future_offset
                        )
                    )
            self._prev_runahead_base_point = runahead_base_point
        if latest_allowed_point > self.stop_point:
            latest_allowed_point = self.stop_point

        for point, itask_id_map in self.runahead_pool.copy().items():
            if point <= latest_allowed_point:
                for itask in itask_id_map.copy().values():
                    self.release_runahead_task(itask)
                    released = True
        return released

    def load_db_task_pool_for_restart(self, row_idx, row):
        """Load a task from previous task pool.

        The state of task prerequisites (satisfied or not) and outputs
        (completed or not) is determined by the recorded TASK_STATUS:

        TASK_STATUS_WAITING    - prerequisites and outputs unsatisified
        TASK_STATUS_HELD       - ditto (only waiting tasks can be held)
        TASK_STATUS_QUEUED     - prereqs satisfied, outputs not completed
                                 (only tasks ready to run can get queued)
        TASK_STATUS_READY      - ditto
        TASK_STATUS_SUBMITTED  - ditto (but see *)
        TASK_STATUS_SUBMIT_RETRYING - ditto
        TASK_STATUS_RUNNING    - ditto (but see *)
        TASK_STATUS_FAILED     - ditto (tasks must run in order to fail)
        TASK_STATUS_RETRYING   - ditto (tasks must fail in order to retry)
        TASK_STATUS_SUCCEEDED  - prerequisites satisfied, outputs completed

        (*) tasks reloaded with TASK_STATUS_SUBMITTED or TASK_STATUS_RUNNING
        are polled to determine what their true status is.
        """
        if row_idx == 0:
            LOG.info("LOADING task proxies")
        (cycle, name, spawned, status, hold_swap, submit_num, _,
         user_at_host, time_submit, time_run, timeout,
         outputs_str) = row
        try:
            itask = TaskProxy(
                self.config.get_taskdef(name),
                get_point(cycle),
                hold_swap=hold_swap,
                has_spawned=bool(spawned),
                submit_num=submit_num)
        except SuiteConfigError as exc:
            if cylc.flags.debug:
                ERR.error(traceback.format_exc())
            else:
                ERR.error(str(exc))
            ERR.warning((
                "ignoring task %s from the suite run database\n"
                "(its task definition has probably been deleted).") % name)
        except Exception:
            ERR.error(traceback.format_exc())
            ERR.error("could not load task %s" % name)
        else:
            if status in (TASK_STATUS_SUBMITTED, TASK_STATUS_RUNNING):
                itask.state.set_prerequisites_all_satisfied()
                # update the task proxy with user@host
                try:
                    itask.task_owner, itask.task_host = user_at_host.split(
                        "@", 1)
                except ValueError:
                    itask.task_owner = None
                    itask.task_host = user_at_host
                if time_submit:
                    itask.set_event_time('submitted', time_submit)
                if time_run:
                    itask.set_event_time('started', time_run)
                if timeout is not None:
                    itask.timeout_timers[status] = timeout

            elif status in (TASK_STATUS_SUBMIT_FAILED, TASK_STATUS_FAILED):
                itask.state.set_prerequisites_all_satisfied()

            elif status in (TASK_STATUS_QUEUED, TASK_STATUS_READY):
                # reset to waiting as these had not been submitted yet.
                status = TASK_STATUS_WAITING
                itask.state.set_prerequisites_all_satisfied()

            elif status in (TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING):
                itask.state.set_prerequisites_all_satisfied()

            elif status == TASK_STATUS_SUCCEEDED:
                itask.state.set_prerequisites_all_satisfied()

            itask.state.reset_state(status)

            # Tasks that are running or finished can have completed custom
            # outputs
            if status in [
                    TASK_STATUS_RUNNING, TASK_STATUS_FAILED,
                    TASK_STATUS_SUCCEEDED]:
                try:
                    for output in outputs_str.splitlines():
                        itask.state.outputs.set_completion(
                            output.split("=", 1)[1], True)
                except AttributeError:
                    pass

            if user_at_host:
                itask.summary['job_hosts'][int(submit_num)] = user_at_host
            if hold_swap:
                LOG.info("+ %s.%s %s (%s)" % (name, cycle, status, hold_swap))
            else:
                LOG.info("+ %s.%s %s" % (name, cycle, status))
            self.add_to_runahead_pool(itask, is_restart=True)

    def load_db_task_action_timers(self, row_idx, row):
        """Load a task action timer, e.g. event handlers, retry states."""
        if row_idx == 0:
            LOG.info("LOADING task action timers")
        (cycle, name, ctx_key_pickle, ctx_pickle, delays_pickle, num, delay,
         timeout) = row
        id_ = TaskID.get(name, cycle)
        ctx_key = "?"
        try:
            ctx_key = pickle.loads(str(ctx_key_pickle))
            ctx = pickle.loads(str(ctx_pickle))
            delays = pickle.loads(str(delays_pickle))
            if ctx_key and ctx_key[0] in ["poll_timers", "try_timers"]:
                itask = self.get_task_by_id(id_)
                if itask is None:
                    ERR.warning("%(id)s: task not found, skip" % {"id": id_})
                    return
                getattr(itask, ctx_key[0])[ctx_key[1]] = TaskActionTimer(
                    ctx, delays, num, delay, timeout)
            else:
                key1, submit_num = ctx_key
                key = (key1, cycle, name, submit_num)
                self.task_events_mgr.event_timers[key] = TaskActionTimer(
                    ctx, delays, num, delay, timeout)
        except (EOFError, TypeError, LookupError, ValueError):
            ERR.warning(
                "%(id)s: skip action timer %(ctx_key)s" %
                {"id": id_, "ctx_key": ctx_key})
            ERR.warning(traceback.format_exc())
            return
        LOG.info("+ %s.%s %s" % (name, cycle, ctx_key))

    def release_runahead_task(self, itask):
        """Release itask to the appropriate queue in the active pool."""
        try:
            queue = self.myq[itask.tdef.name]
        except KeyError:
            queue = self.config.Q_DEFAULT
        self.queues.setdefault(queue, OrderedDict())
        self.queues[queue][itask.identity] = itask
        self.pool.setdefault(itask.point, {})
        self.pool[itask.point][itask.identity] = itask
        self.pool_changed = True
        LOG.debug("released to the task pool", itask=itask)
        del self.runahead_pool[itask.point][itask.identity]
        if not self.runahead_pool[itask.point]:
            del self.runahead_pool[itask.point]
        self.rhpool_changed = True
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

        # remove from queue
        if itask.tdef.name in self.myq:  # A reload can remove a task
            del self.queues[self.myq[itask.tdef.name]][itask.identity]
        del self.pool[itask.point][itask.identity]
        if not self.pool[itask.point]:
            del self.pool[itask.point]
        self.pool_changed = True
        msg = "task proxy removed"
        if reason:
            msg += " (%s)" % reason
        LOG.debug(msg, itask=itask)
        if itask.tdef.max_future_prereq_offset is not None:
            self.set_max_future_offset()
        del itask

    def get_all_tasks(self):
        """Return a list of all task proxies."""
        return self.get_rh_tasks() + self.get_tasks()

    def get_tasks(self):
        """Return a list of task proxies in the main task pool."""
        if self.pool_changed:
            self.pool_changed = False
            self.pool_list = []
            for itask_id_maps in self.queues.values():
                self.pool_list.extend(itask_id_maps.values())
        return self.pool_list

    def get_rh_tasks(self):
        """Return a list of task proxies in the runahead pool."""
        if self.rhpool_changed:
            self.rhpool_changed = False
            self.rhpool_list = []
            for itask_id_maps in self.runahead_pool.values():
                self.rhpool_list.extend(itask_id_maps.values())
        return self.rhpool_list

    def get_tasks_by_point(self, incl_runahead):
        """Return a map of task proxies by cycle point."""
        point_itasks = {}
        for point, itask_id_map in self.pool.items():
            point_itasks[point] = itask_id_map.values()

        if not incl_runahead:
            return point_itasks

        for point, itask_id_map in self.runahead_pool.items():
            point_itasks.setdefault(point, [])
            point_itasks[point].extend(itask_id_map.values())
        return point_itasks

    def get_task_by_id(self, id_):
        """Return task by ID is in the runahead_pool or pool.

        Return None if task does not exist.
        """
        for itask_ids in self.queues.values() + self.runahead_pool.values():
            try:
                return itask_ids[id_]
            except KeyError:
                pass

    def get_ready_tasks(self):
        """
        1) queue tasks that are ready to run (prerequisites satisfied,
        clock-trigger time up) or if their manual trigger flag is set.

        2) then submit queued tasks if their queue limit has not been
        reached or their manual trigger flag is set.

        If TASK_STATUS_QUEUED the task will submit as soon as its internal
        queue allows (or immediately if manually triggered first).

        Use of "cylc trigger" sets a task's manual trigger flag. Then,
        below, an unqueued task will be queued whether or not it is
        ready to run; and a queued task will be submitted whether or not
        its queue limit has been reached. The flag is immediately unset
        after use so that two manual trigger ops are required to submit
        an initially unqueued task that is queue-limited.

        Return the tasks that are dequeued.
        """

        now = time()
        ready_tasks = []
        qconfig = self.config.cfg['scheduling']['queues']

        for queue in self.queues:
            tasks = self.queues[queue].values()

            # 1) queue unqueued tasks that are ready to run or manually forced
            for itask in tasks:
                if itask.state.status != TASK_STATUS_QUEUED:
                    # only need to check that unqueued tasks are ready
                    if itask.manual_trigger or itask.ready_to_run(now):
                        # queue the task
                        itask.state.reset_state(TASK_STATUS_QUEUED)
                        itask.reset_manual_trigger()
                        # move the task to the back of the queue
                        self.queues[queue][itask.identity] = \
                            self.queues[queue].pop(itask.identity)

            # 2) submit queued tasks if manually forced or not queue-limited
            n_active = 0
            n_release = 0
            n_limit = qconfig[queue]['limit']
            tasks = self.queues[queue].values()

            # 2.1) count active tasks and compare to queue limit
            if n_limit:
                for itask in tasks:
                    if itask.state.status in [TASK_STATUS_READY,
                                              TASK_STATUS_SUBMITTED,
                                              TASK_STATUS_RUNNING]:
                        n_active += 1
                n_release = n_limit - n_active

            # 2.2) release queued tasks if not limited or if manually forced
            for itask in tasks:
                if not itask.state.status == TASK_STATUS_QUEUED:
                    # (This excludes tasks remaining TASK_STATUS_READY because
                    # job submission has been stopped with 'cylc shutdown').
                    continue
                if itask.manual_trigger or not n_limit or n_release > 0:
                    # manual release, or no limit, or not currently limited
                    n_release -= 1
                    ready_tasks.append(itask)
                    itask.reset_manual_trigger()
                # else leaved queued

        LOG.debug('%d task(s) de-queued' % len(ready_tasks))

        return ready_tasks

    def task_has_future_trigger_overrun(self, itask):
        """Check for future triggers extending beyond the final cycle."""
        if not self.stop_point:
            return False
        for pct in itask.state.prerequisites_get_target_points():
            if pct > self.stop_point:
                return True
        return False

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

    def get_max_point_runahead(self):
        """Return the maximum cycle point currently in the runahead pool."""
        cycles = self.runahead_pool.keys()
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

    def set_do_reload(self, config, stop_point):
        """Set the task pool to reload mode."""
        self.config = config
        self.do_reload = True

        self.custom_runahead_limit = self.config.get_custom_runahead_limit()
        self.max_num_active_cycle_points = (
            self.config.get_max_num_active_cycle_points())
        self.stop_point = stop_point

        # reassign live tasks from the old queues to the new.
        # self.queues[queue][id_] = task
        self.assign_queues()
        new_queues = {}
        for queue in self.queues:
            for id_, itask in self.queues[queue].items():
                if itask.tdef.name not in self.myq:
                    continue
                key = self.myq[itask.tdef.name]
                new_queues.setdefault(key, OrderedDict())
                new_queues[key][id_] = itask
        self.queues = new_queues

        # find any old tasks that have been removed from the suite
        old_task_name_list = self.task_name_list
        self.task_name_list = self.config.get_task_name_list()
        for name in old_task_name_list:
            if name not in self.task_name_list:
                self.orphans.append(name)
        for name in self.task_name_list:
            if name in self.orphans:
                self.orphans.remove(name)
        # adjust the new suite config to handle the orphans
        self.config.adopt_orphans(self.orphans)

    def reload_taskdefs(self):
        """Reload task definitions."""
        LOG.info("Reloading task definitions.")
        # Log tasks orphaned by a reload that were not in the task pool.
        for task in self.orphans:
            if task not in (tsk.tdef.name for tsk in self.get_all_tasks()):
                LOG.warning("Removed task: '%s'" % (task,))
        for itask in self.get_all_tasks():
            if itask.tdef.name in self.orphans:
                if itask.state.status in [
                        TASK_STATUS_WAITING, TASK_STATUS_QUEUED,
                        TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING,
                        TASK_STATUS_HELD]:
                    # Remove orphaned task if it hasn't started running yet.
                    LOG.warning("(task orphaned by suite reload)", itask=itask)
                    self.remove(itask)
                else:
                    # Keep active orphaned task, but stop it from spawning.
                    itask.has_spawned = True
                    LOG.warning(
                        "last instance (orphaned by reload)", itask=itask)
            else:
                self.remove(itask, '(suite definition reload)')
                new_task = self.add_to_runahead_pool(TaskProxy(
                    self.config.get_taskdef(itask.tdef.name), itask.point,
                    itask.state.status, stop_point=itask.stop_point,
                    submit_num=itask.submit_num))
                new_task.copy_pre_reload(itask)
                LOG.info('reloaded task definition', itask=itask)
                if itask.state.status in TASK_STATUSES_ACTIVE:
                    LOG.warning(
                        "job(%0d2) active with pre-reload settings" %
                        itask.submit_num,
                        itask=itask)
        LOG.info("Reload completed.")
        self.do_reload = False

    def set_stop_point(self, stop_point):
        """Set the global suite stop point."""
        self.stop_point = stop_point
        for itask in self.get_tasks():
            # check cycle stop or hold conditions
            if (self.stop_point and itask.point > self.stop_point and
                    itask.state.status in [TASK_STATUS_WAITING,
                                           TASK_STATUS_QUEUED]):
                LOG.warning(
                    "not running (beyond suite stop cycle) %s" %
                    self.stop_point,
                    itask=itask)
                itask.state.set_held()

    def can_stop(self, stop_mode):
        """Return True if suite can stop.

        A task is considered active if:
        * It is in the active state and not marked with a kill failure.
        * It has pending event handlers.
        """
        if stop_mode is None:
            return False
        if stop_mode == self.STOP_REQUEST_NOW_NOW:
            return True
        if self.task_events_mgr.event_timers:
            return False
        for itask in self.get_tasks():
            if (stop_mode == self.STOP_REQUEST_CLEAN and
                    itask.state.status in TASK_STATUSES_ACTIVE and
                    not itask.state.kill_failed):
                return False
        return True

    def warn_stop_orphans(self):
        """Log (warning) orphaned tasks on suite stop."""
        for itask in self.get_tasks():
            if (itask.state.status in TASK_STATUSES_ACTIVE and
                    itask.state.kill_failed):
                LOG.warning("%s: orphaned task (%s, kill failed)" % (
                    itask.identity, itask.state.status))
            elif itask.state.status in TASK_STATUSES_ACTIVE:
                LOG.warning("%s: orphaned task (%s)" % (
                    itask.identity, itask.state.status))
        for key1, point, name, submit_num in self.task_events_mgr.event_timers:
            LOG.warning("%s/%s/%s: incomplete task event handler %s" % (
                point, name, submit_num, key1))

    def is_stalled(self):
        """Return True if the suite is stalled.

        A suite is stalled when:
        * It is not held.
        * It has no active tasks.
        * It has waiting tasks with unmet prerequisites
          (ignoring clock triggers).
        """
        if self.is_held:
            return False
        can_be_stalled = False
        for itask in self.get_tasks():
            if itask.point > self.stop_point or itask.state.status in [
                    TASK_STATUS_SUCCEEDED, TASK_STATUS_EXPIRED]:
                # Ignore: Task beyond stop point.
                # Ignore: Succeeded and expired tasks.
                continue
            if itask.state.status in TASK_STATUSES_NOT_STALLED or (
                    itask.state.status in TASK_STATUS_HELD and
                    itask.state.hold_swap in TASK_STATUSES_NOT_STALLED):
                # Pool contains active tasks (or held active tasks)
                # Return "not stalled" immediately.
                return False
            if ((itask.state.status == TASK_STATUS_WAITING or
                    itask.state.hold_swap == TASK_STATUS_WAITING) and
                    itask.state.prerequisites_are_all_satisfied()):
                # Waiting tasks with all prerequisites satisfied,
                # probably waiting for clock trigger only.
                # This task can be considered active.
                # Return "not stalled" immediately.
                return False
            # We should be left with (submission) failed tasks and
            # waiting tasks with unsatisfied prerequisites.
            can_be_stalled = True
        return can_be_stalled

    def report_stalled_task_deps(self):
        """Return a set of unmet dependencies"""
        prereqs_map = {}
        for itask in self.get_tasks():
            if ((itask.state.status == TASK_STATUS_WAITING or
                    itask.state.hold_swap == TASK_STATUS_WAITING) and
                    itask.state.prerequisites_are_not_all_satisfied()):
                prereqs_map[itask.identity] = []
                for prereq_str, is_met in itask.state.prerequisites_dump():
                    if not is_met:
                        prereqs_map[itask.identity].append(prereq_str)

        # prune tree to ignore items that are elsewhere in it
        for id_, prereqs in prereqs_map.copy().items():
            for prereq in prereqs:
                prereq_strs = prereq.split()
                if prereq_strs[0] == "LABEL:":
                    unsatisfied_id = prereq_strs[3]
                elif prereq_strs[0] == "CONDITION:":
                    continue
                else:
                    unsatisfied_id = prereq_strs[0]
                # Clear out tasks with dependencies on other waiting tasks
                if unsatisfied_id in prereqs_map:
                    del prereqs_map[id_]
                    break

        for id_, prereqs in prereqs_map.items():
            LOG.warning("Unmet prerequisites for %s:" % id_)
            for prereq in prereqs:
                LOG.warning(" * %s" % prereq)

    def set_hold_point(self, point):
        """Set the point after which tasks must be held."""
        self.hold_point = point
        if point is not None:
            for itask in self.get_all_tasks():
                if itask.point > point:
                    itask.state.set_held()

    def hold_tasks(self, items):
        """Hold tasks with IDs matching any item in "ids"."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            itask.state.set_held()
        return len(bad_items)

    def release_tasks(self, items):
        """Release held tasks with IDs matching any item in "ids"."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            itask.state.unset_held()
        return len(bad_items)

    def hold_all_tasks(self):
        """Hold all tasks."""
        LOG.info("Holding all waiting or queued tasks now")
        self.is_held = True
        for itask in self.get_all_tasks():
            itask.state.set_held()

    def release_all_tasks(self):
        """Release all held tasks."""
        self.is_held = False
        self.release_tasks(None)

    def get_failed_tasks(self):
        """Return failed and submission failed tasks."""
        failed = []
        for itask in self.get_tasks():
            if itask.state.status in [TASK_STATUS_FAILED,
                                      TASK_STATUS_SUBMIT_FAILED]:
                failed.append(itask)
        return failed

    def any_task_failed(self):
        """Return True if any tasks in the pool failed."""
        for itask in self.get_tasks():
            if itask.state.status in [TASK_STATUS_FAILED,
                                      TASK_STATUS_SUBMIT_FAILED]:
                return True
        return False

    def match_dependencies(self):
        """Run time dependency negotiation.

        Tasks attempt to get their prerequisites satisfied by other tasks'
        outputs. Brokered negotiation is O(n) in number of tasks.

        """
        all_task_outputs = set()
        for itask in self.get_tasks():
            for output in itask.state.outputs.get_completed():
                all_task_outputs.add((itask.tdef.name,
                                      str(itask.point),
                                      output))
        for itask in self.get_tasks():
            # Try to satisfy itask if not already satisfied.
            if itask.state.prerequisites_are_not_all_satisfied():
                itask.state.satisfy_me(all_task_outputs)

    def force_spawn(self, itask):
        """Spawn successor of itask."""
        if itask.has_spawned:
            return None
        itask.has_spawned = True
        LOG.debug('forced spawning', itask=itask)
        next_point = itask.next_point()
        if next_point is None:
            return
        new_task = TaskProxy(
            itask.tdef, start_point=next_point, stop_point=itask.stop_point)
        return self.add_to_runahead_pool(new_task)

    def spawn_all_tasks(self):
        """Spawn successors of tasks in pool, if they're ready.

        Return the number of spawned tasks.
        """
        n_spawned = 0
        for itask in self.get_tasks():
            # A task proxy is never ready to spawn if:
            #    * it has spawned already
            #    * its state is submit-failed (avoid running multiple instances
            #      of a task with bad job submission config).
            # Otherwise a task proxy is ready to spawn if either:
            #    * self.tdef.spawn ahead is True (results in spawning out to
            #      max active cycle points), OR
            #    * its state is >= submitted (allows successive instances
            #      to run concurrently, but not out of order).
            if (
                not itask.has_spawned and
                itask.state.status != TASK_STATUS_SUBMIT_FAILED and
                (
                    itask.tdef.spawn_ahead or
                    itask.state.is_greater_than(TASK_STATUS_READY)
                )
            ):
                if self.force_spawn(itask) is not None:
                    n_spawned += 1
        return n_spawned

    def remove_suiciding_tasks(self):
        """Remove any tasks that have suicide-triggered.

        Return the number of removed tasks.
        """
        num_removed = 0
        for itask in self.get_tasks():
            if itask.state.suicide_prerequisites:
                if itask.state.suicide_prerequisites_satisfied():
                    if itask.state.status in [TASK_STATUS_READY,
                                              TASK_STATUS_SUBMITTED,
                                              TASK_STATUS_RUNNING]:
                        LOG.warning('suiciding while active', itask=itask)
                    else:
                        LOG.info('suiciding', itask=itask)
                    self.force_spawn(itask)
                    self.remove(itask, 'suicide')
                    num_removed += 1
        return num_removed

    def _get_earliest_unsatisfied_point(self):
        """Get earliest unsatisfied cycle point."""
        cutoff = None
        for itask in self.get_all_tasks():
            # this has to consider tasks in the runahead pool too, e.g.
            # ones that have just spawned and not been released yet.
            if itask.state.status in [TASK_STATUS_WAITING, TASK_STATUS_HELD]:
                if cutoff is None or itask.point < cutoff:
                    cutoff = itask.point
            elif not itask.has_spawned:
                # (e.g. TASK_STATUS_READY)
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
        implies foo's cutoff is T+12: if foo has succeeded (or expired) and
        spawned, it can be removed if no unsatisfied task proxy exists with
        T<=T+12. Note this only uses information about the cycle point of
        downstream dependents - if we used specific IDs instead spent
        tasks could be identified and removed even earlier).

        Return the number of removed tasks.
        """
        spent = []

        # first find the cycle point of the earliest unsatisfied task
        cutoff = self._get_earliest_unsatisfied_point()
        if not cutoff:
            return len(spent)

        # now check each succeeded task against the cutoff
        for itask in self.get_tasks():
            if (itask.state.status in [TASK_STATUS_SUCCEEDED,
                                       TASK_STATUS_EXPIRED] and
                    itask.has_spawned and
                    itask.cleanup_cutoff is not None and
                    cutoff > itask.cleanup_cutoff):
                spent.append(itask)
        for itask in spent:
            self.remove(itask)
        return len(spent)

    def spawn_tasks(self, items):
        """Force tasks to spawn successors if they haven't already.

        """
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            if not itask.has_spawned:
                LOG.info("forced spawning", itask=itask)
                self.force_spawn(itask)
        return len(bad_items)

    def reset_task_states(self, items, status, outputs):
        """Reset task states."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            if status and status != itask.state.status:
                LOG.info("resetting state to %s" % status, itask=itask)
                if status == TASK_STATUS_READY:
                    # Pseudo state (in this context) -
                    # set waiting and satisified.
                    itask.state.reset_state(TASK_STATUS_WAITING)
                    itask.state.set_prerequisites_all_satisfied()
                    itask.state.unset_special_outputs()
                    itask.state.outputs.set_all_incomplete()
                else:
                    itask.state.reset_state(status)
                    if status in [
                            TASK_STATUS_FAILED, TASK_STATUS_SUBMIT_FAILED]:
                        itask.set_event_time('finished',
                                             get_current_time_string())
            if outputs:
                for output in outputs:
                    is_completed = True
                    if output.startswith('!'):
                        is_completed = False
                        output = output[1:]
                    if output == '*' and is_completed:
                        itask.state.outputs.set_all_completed()
                        LOG.info("reset all output to completed", itask=itask)
                    elif output == '*':
                        itask.state.outputs.set_all_incomplete()
                        LOG.info("reset all output to incomplete", itask=itask)
                    else:
                        ret = itask.state.outputs.set_msg_trg_completion(
                            message=output, is_completed=is_completed)
                        if ret is None:
                            ret = itask.state.outputs.set_msg_trg_completion(
                                trigger=output, is_completed=is_completed)
                        if ret is None:
                            LOG.warning(
                                "cannot reset output: %s" % output,
                                itask=itask)
                        elif ret:
                            LOG.info(
                                "reset output to complete: %s" % output,
                                itask=itask)
                        else:
                            LOG.info(
                                "reset output to incomplete: %s" % output,
                                itask=itask)
                self.suite_db_mgr.put_update_task_outputs(itask)
        return len(bad_items)

    def remove_tasks(self, items, spawn=False):
        """Remove tasks from pool."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            if spawn:
                self.force_spawn(itask)
            self.remove(itask, 'by request')
        return len(bad_items)

    def trigger_tasks(self, items, back_out=False):
        """Trigger tasks."""
        itasks, bad_items = self.filter_task_proxies(items)
        n_warnings = len(bad_items)
        for itask in itasks:
            if back_out:
                # (Aborted edit-run, reset for next trigger attempt).
                itask.submit_num -= 1
                itask.local_job_file_path = None
                continue
            if itask.state.status in TASK_STATUSES_ACTIVE:
                LOG.warning('%s: already triggered' % itask.identity)
                n_warnings += 1
                continue
            itask.manual_trigger = True
            if not itask.state.status == TASK_STATUS_QUEUED:
                itask.state.reset_state(TASK_STATUS_READY)
        return n_warnings

    def check_auto_shutdown(self):
        """Check if we should do a normal automatic shutdown."""
        shutdown = True
        for itask in self.get_all_tasks():
            if self.stop_point is None:
                # Don't if any unsucceeded task exists.
                if itask.state.status not in [
                        TASK_STATUS_SUCCEEDED, TASK_STATUS_EXPIRED]:
                    shutdown = False
                    break
            elif (itask.point <= self.stop_point and
                    itask.state.status not in [TASK_STATUS_SUCCEEDED,
                                               TASK_STATUS_EXPIRED]):
                # Don't if any unsucceeded task exists < stop point...
                if itask.identity not in self.held_future_tasks:
                    # ...unless it has a future trigger extending > stop point.
                    shutdown = False
                    break
        return shutdown

    def sim_time_check(self, message_queue):
        """Simulation mode: simulate task run times and set states."""
        sim_task_state_changed = False
        for itask in self.get_tasks():
            if itask.state.status != TASK_STATUS_RUNNING:
                continue
            timeout = (itask.summary['started_time'] +
                       itask.tdef.rtconfig['job']['simulated run length'])
            if time() > timeout:
                conf = itask.tdef.rtconfig['simulation']
                if (itask.point in conf['fail cycle points'] and
                        (itask.get_try_num() == 1 or
                         not conf['fail try 1 only'])):
                    message_queue.put(
                        (itask.identity, 'CRITICAL', TASK_STATUS_FAILED))
                else:
                    # Simulate message outputs.
                    for msg in itask.tdef.rtconfig['outputs'].values():
                        message_queue.put((itask.identity, 'NORMAL', msg))
                    message_queue.put(
                        (itask.identity, 'NORMAL', TASK_STATUS_SUCCEEDED))
                sim_task_state_changed = True
        return sim_task_state_changed

    def set_expired_tasks(self):
        """Check if any waiting tasks expired.

        Set their status accordingly.
        """
        now = time()
        for itask in self.get_tasks():
            if (itask.state.status != TASK_STATUS_WAITING or
                    itask.tdef.expiration_offset is None):
                continue
            if itask.expire_time is None:
                itask.expire_time = (
                    itask.get_point_as_seconds() +
                    itask.get_offset_as_seconds(itask.tdef.expiration_offset))
            if now > itask.expire_time:
                msg = 'Task expired (skipping job).'
                LOG.warning(msg, itask=itask)
                self.task_events_mgr.setup_event_handlers(
                    itask, "expired", msg)
                itask.state.reset_state(TASK_STATUS_EXPIRED)

    def waiting_tasks_ready(self):
        """Waiting tasks can become ready for internal reasons.

        Namely clock-triggers or retry-delay timers

        """
        now = time()
        result = False
        for itask in self.get_tasks():
            if itask.ready_to_run(now):
                result = True
                break
        return result

    def task_succeeded(self, id_):
        """Return True if task with id_ is in the succeeded state."""
        for itask in self.get_tasks():
            if (itask.identity == id_ and
                    itask.state.status == TASK_STATUS_SUCCEEDED):
                return True
        return False

    def ping_task(self, id_, exists_only=False):
        """Return message to indicate if task exists and/or is running."""
        found = False
        running = False
        for itask in self.get_tasks():
            if itask.identity == id_:
                found = True
                if itask.state.status == TASK_STATUS_RUNNING:
                    running = True
                break
        if running:
            return True, " running"
        elif found and exists_only:
            return True, "task found"
        elif found:
            return False, "task not running"
        else:
            return False, "task not found"

    def get_task_requisites(self, items, list_prereqs=False):
        """Return task prerequisites.

        Result in a dict of a dict:
        {
            "task_id": {
                "meta": {key: value, ...},
                "prerequisites": {key: value, ...},
                "outputs": {key: value, ...},
                "extras": {key: value, ...},
            },
            ...
        }
        """
        itasks, bad_items = self.filter_task_proxies(items)
        results = {}
        now = time()
        for itask in itasks:
            if list_prereqs:
                results[itask.identity] = {
                    'prerequisites': itask.state.prerequisites_dump(
                        list_prereqs=True)}
                continue

            extras = {}
            if itask.tdef.clocktrigger_offset is not None:
                extras['Clock trigger time reached'] = (
                    itask.start_time_reached(now))
                extras['Triggers at'] = get_time_string_from_unix_time(
                    itask.delayed_start)
            for trig, satisfied in itask.state.external_triggers.items():
                if satisfied:
                    state = 'satisfied'
                else:
                    state = 'NOT satisfied'
                extras['External trigger "%s"' % trig] = state

            outputs = []
            for _, msg, is_completed in itask.state.outputs.get_all():
                outputs.append(["%s %s" % (itask.identity, msg), is_completed])
            results[itask.identity] = {
                "meta": itask.tdef.describe(),
                "prerequisites": itask.state.prerequisites_dump(),
                "outputs": outputs,
                "extras": extras}
        return results, bad_items

    def filter_task_proxies(self, items):
        """Return task proxies that match names, points, states in items.

        Return (itasks, bad_items).
        In the new form, the arguments should look like:
        items -- a list of strings for matching task proxies, each with
                 the general form name[.point][:state] or [point/]name[:state]
                 where name is a glob-like pattern for matching a task name or
                 a family name.

        """
        itasks = []
        bad_items = []
        if not items:
            itasks += self.get_all_tasks()
        else:
            for item in items:
                point_str, name_str, status = self._parse_task_item(item)
                if point_str is None:
                    point_str = "*"
                else:
                    try:
                        point_str = standardise_point_string(point_str)
                    except ValueError:
                        # point_str may be a glob
                        pass
                tasks_found = False
                for itask in self.get_all_tasks():
                    nss = itask.tdef.namespace_hierarchy
                    if (fnmatchcase(str(itask.point), point_str) and
                            (not status or itask.state.status == status) and
                            (fnmatchcase(itask.tdef.name, name_str) or
                             any(fnmatchcase(ns, name_str) for ns in nss))):
                        itasks.append(itask)
                        tasks_found = True
                if not tasks_found:
                    LOG.warning(self.ERR_PREFIX_TASKID_MATCH + item)
                    bad_items.append(item)
        return itasks, bad_items

    @classmethod
    def _parse_task_item(cls, item):
        """Parse point/name:state or name.point:state syntax."""
        if ":" in item:
            head, state_str = item.rsplit(":", 1)
        else:
            head, state_str = (item, None)
        if "/" in head:
            point_str, name_str = head.split("/", 1)
        elif "." in head:
            name_str, point_str = head.split(".", 1)
        else:
            name_str, point_str = (head, None)
        return (point_str, name_str, state_str)
