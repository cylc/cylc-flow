#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
from logging import DEBUG, INFO, WARNING
import pickle
import Queue
from random import randrange
from time import time

from cylc.config import SuiteConfig
from cylc.cycling.loader import (
    get_interval, get_interval_cls, get_point, ISO8601_CYCLING_TYPE,
    standardise_point_string)
import cylc.flags
from cylc.network.ext_trigger_server import ExtTriggerServer
from cylc.network.suite_broadcast_server import BroadcastServer
from cylc.rundb import CylcSuiteDAO
from cylc.suite_logging import LOG
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


class TaskPool(object):
    """Task pool of a suite."""

    ERR_PREFIX_TASKID_MATCH = "No matching tasks found: "
    ERR_PREFIX_TASK_NOT_ON_SEQUENCE = "Invalid cycle point for task: "

    STOP_AUTO = 'AUTOMATIC'
    STOP_AUTO_ON_TASK_FAILURE = 'AUTOMATIC(ON-TASK-FAILURE)'
    STOP_REQUEST_CLEAN = 'REQUEST(CLEAN)'
    STOP_REQUEST_NOW = 'REQUEST(NOW)'
    STOP_REQUEST_NOW_NOW = 'REQUEST(NOW-NOW)'

    TABLE_SUITE_PARAMS = CylcSuiteDAO.TABLE_SUITE_PARAMS
    TABLE_SUITE_TEMPLATE_VARS = CylcSuiteDAO.TABLE_SUITE_TEMPLATE_VARS
    TABLE_TASK_POOL = CylcSuiteDAO.TABLE_TASK_POOL
    TABLE_TASK_ACTION_TIMERS = CylcSuiteDAO.TABLE_TASK_ACTION_TIMERS
    TABLE_CHECKPOINT_ID = CylcSuiteDAO.TABLE_CHECKPOINT_ID

    def __init__(self, stop_point, pri_dao, pub_dao, task_events_mgr):
        self.stop_point = stop_point
        self.pri_dao = pri_dao
        self.pub_dao = pub_dao
        self.task_events_mgr = task_events_mgr

        self.do_reload = False
        config = SuiteConfig.get_inst()
        self.custom_runahead_limit = config.get_custom_runahead_limit()
        self.max_future_offset = None
        self._prev_runahead_base_point = None
        self.max_num_active_cycle_points = (
            config.get_max_num_active_cycle_points())
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
        self.task_name_list = config.get_task_name_list()

        self.db_deletes_map = {
            self.TABLE_SUITE_PARAMS: [],
            self.TABLE_TASK_POOL: [],
            self.TABLE_TASK_ACTION_TIMERS: []}
        self.db_inserts_map = {
            self.TABLE_SUITE_PARAMS: [],
            self.TABLE_SUITE_TEMPLATE_VARS: [],
            self.TABLE_CHECKPOINT_ID: [],
            self.TABLE_TASK_POOL: [],
            self.TABLE_TASK_ACTION_TIMERS: []}

    def assign_queues(self):
        """self.myq[taskname] = qfoo"""
        config = SuiteConfig.get_inst()
        qconfig = config.cfg['scheduling']['queues']
        self.myq = {}
        for queue in qconfig:
            for taskname in qconfig[queue]['members']:
                self.myq[taskname] = queue

    def insert_tasks(self, items, stop_point_str, no_check=False):
        """Insert tasks."""
        n_warnings = 0
        config = SuiteConfig.get_inst()
        names = config.get_task_name_list()
        fams = config.runtime['first-parent descendants']
        task_ids = []
        for item in items:
            point_str, name_str, _ = self._parse_task_item(item)
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
            i_names = []
            if name_str in names:
                i_names.append(name_str)
            elif name_str in fams:
                for name in fams[name_str]:
                    if name in names:
                        i_names.append(name)
            else:
                for name in names:
                    if fnmatchcase(name, name_str):
                        i_names.append(name)
                for fam, fam_names in fams.items():
                    if not fnmatchcase(fam, name_str):
                        continue
                    for name in fam_names:
                        if name in names:
                            i_names.append(name)
            if i_names:
                for name in i_names:
                    task_ids.append((name, point_str))
            else:
                LOG.warning(self.ERR_PREFIX_TASKID_MATCH + item)
                n_warnings += 1
                continue
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
        task_states_data = self.pri_dao.select_task_states_by_task_ids(
            ["submit_num"], task_ids)
        for name_str, point_str in task_ids:
            # TODO - insertion of start-up tasks? (startup=False assumed here)

            # Check that the cycle point is on one of the tasks sequences.
            on_sequence = False
            point = get_point(point_str)
            if not no_check:  # Check if cycle point is on the tasks sequence.
                for sequence in config.taskdefs[name_str].sequences:
                    if sequence.is_on_sequence(point):
                        on_sequence = True
                        break
                if not on_sequence:
                    LOG.warning("%s%s, %s" % (
                        self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE, name_str,
                        point_str))
                    continue

            submit_num = None
            if (name_str, point_str) in task_states_data:
                submit_num = task_states_data[(name_str, point_str)].get(
                    "submit_num")
            new_task = TaskProxy(
                config.get_taskdef(name_str), get_point(point_str),
                stop_point=stop_point, submit_num=submit_num)
            if new_task:
                self.add_to_runahead_pool(new_task)
        return n_warnings

    def add_to_runahead_pool(self, itask):
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
            return False

        # do not add if an inserted task is beyond its own stop point
        # (note this is not the same as recurrence bounds)
        if itask.stop_point and itask.point > itask.stop_point:
            LOG.info(
                '%s not adding to pool: beyond task stop cycle' %
                itask.identity)
            return False

        # add in held state if beyond the suite hold point
        if self.hold_point and itask.point > self.hold_point:
            itask.log(
                INFO,
                "holding (beyond suite hold point) " + str(self.hold_point))
            itask.state.reset_state(TASK_STATUS_HELD)
        elif (itask.point <= self.stop_point and
                self.task_has_future_trigger_overrun(itask)):
            itask.log(INFO, "holding (future trigger beyond stop point)")
            self.held_future_tasks.append(itask.identity)
            itask.state.reset_state(TASK_STATUS_HELD)
        elif self.is_held and itask.state.status == TASK_STATUS_WAITING:
            # Hold newly-spawned tasks in a held suite (e.g. due to manual
            # triggering of a held task).
            itask.state.reset_state(TASK_STATUS_HELD)

        # add to the runahead pool
        self.runahead_pool.setdefault(itask.point, {})
        self.runahead_pool[itask.point][itask.identity] = itask
        self.rhpool_changed = True
        return True

    def release_runahead_tasks(self):
        """Release tasks from the runahead pool to the main pool.

        Return True if any tasks are released, else False.
        """

        if not self.runahead_pool:
            return False

        # Any finished tasks can be released immediately (this can happen at
        # restart when all tasks are initially loaded into the runahead pool).
        for itask_id_maps in self.runahead_pool.values():
            for itask in itask_id_maps.values():
                if itask.state.status in [TASK_STATUS_FAILED,
                                          TASK_STATUS_SUCCEEDED,
                                          TASK_STATUS_EXPIRED]:
                    self.release_runahead_task(itask)
                    self.rhpool_changed = True

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
            config = SuiteConfig.get_inst()
            for sequence in config.sequences:
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

        released = False
        for point, itask_id_map in self.runahead_pool.items():
            if point <= latest_allowed_point:
                for itask in itask_id_map.values():
                    self.release_runahead_task(itask)
                    released = True
        return released

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
            msg += " (" + reason + ")"
        itask.log(DEBUG, msg)
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

        # 1) queue unqueued tasks that are ready to run or manually forced
        for itask in self.get_tasks():
            if not itask.state.status == TASK_STATUS_QUEUED:
                # only need to check that unqueued tasks are ready
                if itask.manual_trigger or itask.ready_to_run():
                    # queue the task
                    itask.state.set_state(TASK_STATUS_QUEUED)
                    itask.reset_manual_trigger()

        # 2) submit queued tasks if manually forced or not queue-limited
        ready_tasks = []
        config = SuiteConfig.get_inst()
        qconfig = config.cfg['scheduling']['queues']
        for queue in self.queues:
            # 2.1) count active tasks and compare to queue limit
            n_active = 0
            n_release = 0
            n_limit = qconfig[queue]['limit']
            tasks = self.queues[queue].values()
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
        for pct in set(itask.state.prerequisites_get_target_points()):
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
            LOG.warning("setting NO custom runahead limit")
            self.custom_runahead_limit = None
        else:
            LOG.info("setting custom runahead limit to %s" % interval)
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

    def reconfigure(self, stop_point):
        """Set the task pool to reload mode."""
        self.do_reload = True

        config = SuiteConfig.get_inst()
        self.custom_runahead_limit = config.get_custom_runahead_limit()
        self.max_num_active_cycle_points = (
            config.get_max_num_active_cycle_points())
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
                if key not in new_queues:
                    new_queues[key] = {}
                new_queues[key][id_] = itask
        self.queues = new_queues

        # find any old tasks that have been removed from the suite
        old_task_name_list = self.task_name_list
        self.task_name_list = config.get_task_name_list()
        for name in old_task_name_list:
            if name not in self.task_name_list:
                self.orphans.append(name)
        for name in self.task_name_list:
            if name in self.orphans:
                self.orphans.remove(name)
        # adjust the new suite config to handle the orphans
        config.adopt_orphans(self.orphans)

    def reload_taskdefs(self):
        """Reload task definitions."""
        LOG.info("Reloading task definitions.")
        # Log tasks orphaned by a reload that were not in the task pool.
        for task in self.orphans:
            if task not in [tsk.tdef.name for tsk in self.get_all_tasks()]:
                LOG.warning("Removed task: '%s'" % (task,))
        config = SuiteConfig.get_inst()
        for itask in self.get_all_tasks():
            if itask.tdef.name in self.orphans:
                if itask.state.status in [
                        TASK_STATUS_WAITING, TASK_STATUS_QUEUED,
                        TASK_STATUS_SUBMIT_RETRYING, TASK_STATUS_RETRYING,
                        TASK_STATUS_HELD]:
                    # Remove orphaned task if it hasn't started running yet.
                    itask.log(WARNING, "(task orphaned by suite reload)")
                    self.remove(itask)
                else:
                    # Keep active orphaned task, but stop it from spawning.
                    itask.has_spawned = True
                    itask.log(WARNING, "last instance (orphaned by reload)")
            else:
                new_task = TaskProxy(
                    config.get_taskdef(itask.tdef.name), itask.point,
                    itask.state.status, stop_point=itask.stop_point,
                    submit_num=itask.submit_num, is_reload_or_restart=True,
                    pre_reload_inst=itask)
                self.remove(itask, '(suite definition reload)')
                self.add_to_runahead_pool(new_task)
        LOG.info("Reload completed.")
        self.do_reload = False
        self.pri_dao.take_checkpoints("reload-done", other_daos=[self.pub_dao])

    def set_stop_point(self, stop_point):
        """Set the global suite stop point."""
        self.stop_point = stop_point
        for itask in self.get_tasks():
            # check cycle stop or hold conditions
            if (self.stop_point and itask.point > self.stop_point and
                    itask.state.status in [TASK_STATUS_WAITING,
                                           TASK_STATUS_QUEUED]):
                itask.log(WARNING,
                          "not running (beyond suite stop cycle) " +
                          str(self.stop_point))
                itask.state.reset_state(TASK_STATUS_HELD)

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
        * It has no active tasks.
        * It has waiting tasks with unmet prerequisites
          (ignoring clock triggers).
        """
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

    def get_hold_point(self):
        """Return the point after which tasks must be held."""
        return self.hold_point

    def set_hold_point(self, point):
        """Set the point after which tasks must be held."""
        self.hold_point = point
        if point is not None:
            for itask in self.get_all_tasks():
                if itask.point > point:
                    itask.state.reset_state(TASK_STATUS_HELD)

    def hold_tasks(self, items):
        """Hold tasks with IDs matching any item in "ids"."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            itask.state.reset_state(TASK_STATUS_HELD)
        return len(bad_items)

    def release_tasks(self, items):
        """Release held tasks with IDs matching any item in "ids"."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            itask.state.release()
        return len(bad_items)

    def hold_all_tasks(self):
        """Hold all tasks."""
        LOG.info("Holding all waiting or queued tasks now")
        self.is_held = True
        for itask in self.get_all_tasks():
            itask.state.reset_state(TASK_STATUS_HELD)
        self.db_inserts_map[self.TABLE_SUITE_PARAMS].append(
            {"key": "is_held", "value": 1})

    def release_all_tasks(self):
        """Release all held tasks."""
        self.is_held = False
        self.release_tasks(None)
        self.db_deletes_map[self.TABLE_SUITE_PARAMS].append({"key": "is_held"})

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
        all_outputs = {}   # all_outputs[message] = taskid
        for itask in self.get_tasks():
            all_outputs.update(itask.state.outputs.completed)
        all_output_msgs = set(all_outputs)
        for itask in self.get_tasks():
            # Try to satisfy itask if not already satisfied.
            if itask.state.prerequisites_are_not_all_satisfied():
                itask.state.satisfy_me(all_output_msgs, all_outputs)

    def process_queued_task_messages(self, message_queue):
        """Handle incoming task messages for each task proxy."""
        queue = message_queue.get_queue()
        task_id_messages = {}
        while queue.qsize():
            try:
                task_id, priority, message = queue.get(block=False)
            except Queue.Empty:
                break
            queue.task_done()
            task_id_messages.setdefault(task_id, [])
            task_id_messages[task_id].append((priority, message))
        for itask in self.get_tasks():
            if itask.identity in task_id_messages:
                for priority, message in task_id_messages[itask.identity]:
                    itask.process_incoming_message(priority, message)

    def process_queued_db_ops(self):
        """Handle queued db operations for each task proxy."""
        for itask in self.get_all_tasks():
            # (runahead pool tasks too, to get new state recorders).
            if any(itask.db_inserts_map.values()):
                for table_name, db_inserts in sorted(
                        itask.db_inserts_map.items()):
                    while db_inserts:
                        db_insert = db_inserts.pop(0)
                        db_insert.update({
                            "name": itask.tdef.name,
                            "cycle": str(itask.point),
                        })
                        if "submit_num" not in db_insert:
                            db_insert["submit_num"] = itask.submit_num
                        self.pri_dao.add_insert_item(table_name, db_insert)
                        self.pub_dao.add_insert_item(table_name, db_insert)

            if any(itask.db_updates_map.values()):
                for table_name, db_updates in sorted(
                        itask.db_updates_map.items()):
                    while db_updates:
                        set_args = db_updates.pop(0)
                        where_args = {
                            "cycle": str(itask.point),
                            "name": itask.tdef.name
                        }
                        if "submit_num" not in set_args:
                            where_args["submit_num"] = itask.submit_num
                        self.pri_dao.add_update_item(
                            table_name, set_args, where_args)
                        self.pub_dao.add_update_item(
                            table_name, set_args, where_args)

        # Record suite parameters and tasks in pool
        # Record any broadcast settings to be dumped out
        for obj in self, BroadcastServer.get_inst():
            if any(obj.db_deletes_map.values()):
                for table_name, db_deletes in sorted(
                        obj.db_deletes_map.items()):
                    while db_deletes:
                        where_args = db_deletes.pop(0)
                        self.pri_dao.add_delete_item(table_name, where_args)
                        self.pub_dao.add_delete_item(table_name, where_args)
            if any(obj.db_inserts_map.values()):
                for table_name, db_inserts in sorted(
                        obj.db_inserts_map.items()):
                    while db_inserts:
                        db_insert = db_inserts.pop(0)
                        self.pri_dao.add_insert_item(table_name, db_insert)
                        self.pub_dao.add_insert_item(table_name, db_insert)

        # Previously, we used a separate thread for database writes. This has
        # now been removed. For the private database, there is no real
        # advantage in using a separate thread as it needs to be always in sync
        # with what is current. For the public database, which does not need to
        # be fully in sync, there is some advantage of using a separate
        # thread/process, if writing to it becomes a bottleneck. At the moment,
        # there is no evidence that this is a bottleneck, so it is better to
        # keep the logic simple.
        self.pri_dao.execute_queued_items()
        self.pub_dao.execute_queued_items()

    def force_spawn(self, itask):
        """Spawn successor of itask."""
        if itask.has_spawned:
            return None
        itask.has_spawned = True
        itask.log(DEBUG, 'forced spawning')
        next_point = itask.next_point()
        if next_point is None:
            return
        new_task = TaskProxy(
            itask.tdef, start_point=next_point, stop_point=itask.stop_point)
        if self.add_to_runahead_pool(new_task):
            return new_task
        else:
            return None

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
                if itask.state.suicide_prerequisites_are_all_satisfied():
                    if itask.state.status in [TASK_STATUS_READY,
                                              TASK_STATUS_SUBMITTED,
                                              TASK_STATUS_RUNNING]:
                        itask.log(WARNING, 'suiciding while active')
                    else:
                        itask.log(INFO, 'suiciding')
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
                itask.log(INFO, "forced spawning")
                self.force_spawn(itask)
        return len(bad_items)

    def reset_task_states(self, items, status):
        """Reset task states."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            itask.log(INFO, "resetting state to %s" % status)
            if status == TASK_STATUS_READY:
                # Pseudo state (in this context) - set waiting and satisified.
                itask.state.reset_state(TASK_STATUS_WAITING)
                itask.state.set_prerequisites_all_satisfied()
                itask.state.unset_special_outputs()
                itask.state.outputs.set_all_incomplete()
            elif status in [TASK_STATUS_FAILED, TASK_STATUS_SUBMIT_FAILED]:
                itask.state.reset_state(status)
                time_ = time()
                itask.summary['finished_time'] = time_
                itask.summary['finished_time_string'] = (
                    get_time_string_from_unix_time(time_))
            else:
                itask.state.reset_state(status)
        return len(bad_items)

    def remove_tasks(self, items, spawn=False):
        """Remove tasks from pool."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            if spawn:
                self.force_spawn(itask)
            self.remove(itask, 'by request')
        return len(bad_items)

    def trigger_tasks(self, items):
        """Trigger tasks."""
        itasks, bad_items = self.filter_task_proxies(items)
        n_warnings = len(bad_items)
        for itask in itasks:
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
            if time.time() > timeout:
                # Time up.
                if itask.sim_job_fail():
                    message_queue.put(
                        itask.identity, 'CRITICAL', TASK_STATUS_FAILED)
                else:
                    # Simulate message outputs.
                    for msg in itask.tdef.rtconfig['outputs'].values():
                        message_queue.put(itask.identity, 'NORMAL', msg)
                    message_queue.put(
                        itask.identity, 'NORMAL', TASK_STATUS_SUCCEEDED)
                sim_task_state_changed = True
        return sim_task_state_changed

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
                "descriptions": {key: value, ...},
                "prerequisites": {key: value, ...},
                "outputs": {key: value, ...},
                "extras": {key: value, ...},
            },
            ...
        }
        """
        itasks, bad_items = self.filter_task_proxies(items)
        results = {}
        for itask in itasks:
            if list_prereqs:
                results[itask.identity] = {
                    'prerequisites': itask.state.prerequisites_dump(
                        list_prereqs=True)}
                continue

            extras = {}
            if itask.tdef.clocktrigger_offset is not None:
                extras['Clock trigger time reached'] = (
                    itask.start_time_reached())
                extras['Triggers at'] = get_time_string_from_unix_time(
                    itask.delayed_start)
            for trig, satisfied in itask.state.external_triggers.items():
                if satisfied:
                    state = 'satisfied'
                else:
                    state = 'NOT satisfied'
                extras['External trigger "%s"' % trig] = state

            results[itask.identity] = {
                "descriptions": itask.tdef.describe(),
                "prerequisites": itask.state.prerequisites_dump(),
                "outputs": itask.state.outputs.dump(),
                "extras": extras}
        return results, bad_items

    def match_ext_triggers(self):
        """See if any queued external event messages can trigger tasks."""
        ets = ExtTriggerServer.get_inst()
        for itask in self.get_tasks():
            if itask.state.external_triggers:
                ets.retrieve(itask)

    def put_rundb_suite_params(
            self, run_mode, initial_point, final_point,
            cycle_point_format=None):
        """Put run mode, initial/final cycle point in runtime database.

        This method queues the relevant insert statements.
        """
        self.db_inserts_map[self.TABLE_SUITE_PARAMS].extend([
            {"key": "run_mode", "value": run_mode},
            {"key": "initial_point", "value": str(initial_point)},
            {"key": "final_point", "value": str(final_point)},
        ])
        if cycle_point_format:
            self.db_inserts_map[self.TABLE_SUITE_PARAMS].extend([
                {"key": "cycle_point_format", "value": str(cycle_point_format)}
            ])
        if self.is_held:
            self.db_inserts_map[self.TABLE_SUITE_PARAMS].append(
                {"key": "is_held", "value": 1})

    def put_rundb_suite_template_vars(self, template_vars):
        """Put template_vars in runtime database.

        This method queues the relevant insert statements.
        """
        for key, value in template_vars.items():
            self.db_inserts_map[self.TABLE_SUITE_TEMPLATE_VARS].append(
                {"key": key, "value": value})

    def put_rundb_task_pool(self):
        """Put statements to update the task_pool table in runtime database.

        Update the task_pool table and the task_action_timers table.
        Queue delete (everything) statements to wipe the tables, and queue the
        relevant insert statements for the current tasks in the pool.
        """
        self.db_deletes_map[self.TABLE_TASK_POOL].append({})
        self.db_deletes_map[self.TABLE_TASK_ACTION_TIMERS].append({})
        for itask in self.get_all_tasks():
            self.db_inserts_map[self.TABLE_TASK_POOL].append({
                "name": itask.tdef.name,
                "cycle": str(itask.point),
                "spawned": int(itask.has_spawned),
                "status": itask.state.status,
                "hold_swap": itask.state.hold_swap})
            for ctx_key_0 in ["poll_timers", "try_timers"]:
                for ctx_key_1, timer in getattr(itask, ctx_key_0).items():
                    if timer is None:
                        continue
                    self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                        "name": itask.tdef.name,
                        "cycle": str(itask.point),
                        "ctx_key_pickle": pickle.dumps((ctx_key_0, ctx_key_1)),
                        "ctx_pickle": pickle.dumps(timer.ctx),
                        "delays_pickle": pickle.dumps(timer.delays),
                        "num": timer.num,
                        "delay": timer.delay,
                        "timeout": timer.timeout})
        for key, (itask, timer) in self.task_events_mgr.event_timers.items():
            key1, point, name, submit_num = key
            self.db_inserts_map[self.TABLE_TASK_ACTION_TIMERS].append({
                "name": name,
                "cycle": point,
                "ctx_key_pickle": pickle.dumps((key1, submit_num,)),
                "ctx_pickle": pickle.dumps(timer.ctx),
                "delays_pickle": pickle.dumps(timer.delays),
                "num": timer.num,
                "delay": timer.delay,
                "timeout": timer.timeout})
        self.db_inserts_map[self.TABLE_CHECKPOINT_ID].append({
            # id = -1 for latest
            "id": CylcSuiteDAO.CHECKPOINT_LATEST_ID,
            "time": get_current_time_string(),
            "event": CylcSuiteDAO.CHECKPOINT_LATEST_EVENT})

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
                             any([fnmatchcase(ns, name_str) for ns in nss]))):
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
