# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

"""Wrangle task proxies to manage the workflow."""

from collections import Counter
from fnmatch import fnmatchcase
from string import ascii_letters
import json
from time import time
from typing import Dict, Iterable, List, Optional, Set, TYPE_CHECKING, Tuple

from cylc.flow import LOG
from cylc.flow.cycling.loader import get_point, standardise_point_string
from cylc.flow.cycling.integer import IntegerInterval
from cylc.flow.cycling.iso8601 import ISO8601Interval
from cylc.flow.exceptions import WorkflowConfigError, PointParsingError
from cylc.flow.workflow_status import StopMode
from cylc.flow.task_action_timer import TaskActionTimer, TimerFlags
from cylc.flow.task_events_mgr import (
    CustomTaskEventHandlerContext, TaskEventMailContext,
    TaskJobLogsRetrieveContext)
from cylc.flow.task_id import TaskID
from cylc.flow.task_job_logs import get_task_job_id
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUSES_ACTIVE,
    TASK_STATUSES_FAILURE,
    TASK_STATUS_WAITING,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_FAILED,
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.platforms import get_platform
from cylc.flow.task_queues.independent import IndepQueueManager

if TYPE_CHECKING:
    from cylc.flow.config import WorkflowConfig
    from cylc.flow.cycling import IntervalBase, PointBase
    from cylc.flow.data_store_mgr import DataStoreMgr
    from cylc.flow.task_events_mgr import TaskEventsManager
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager

Pool = Dict['PointBase', Dict[str, TaskProxy]]


class FlowLabelMgr:
    """
    Manage flow labels consisting of a string of one or more letters [a-zA-Z].

    Flow labels are task attributes representing the flow the task belongs to,
    passed down to spawned children. If a new flow is started, a new single
    character label is chosen randomly. This allows for 52 simultaneous flows
    (which should be more than enough) with labels that are easy to work with.

    Flows merge locally when a task can't be spawned because it already exists
    in the pool with a different label. We merge the labels at such tasks so
    that downstream events can be considered to belong to either of the
    original flows. Merged labels are simple strings that contains the
    component labels, e.g. if flow "a" merges with flow "b" the merged result
    is "ab" (or "ba", it doesn't matter which).

    """
    def __init__(self):
        """Store available and used labels."""
        self.avail = set(ascii_letters)
        self.inuse = set()

    def get_num_inuse(self):
        """Return the number of labels currently in use."""
        return len(list(self.inuse))

    def make_avail(self, labels):
        """Return labels (set) to the pool of available labels."""
        LOG.info("returning flow label(s) %s", labels)
        for label in labels:
            try:
                self.inuse.remove(label)
            except KeyError:
                pass
            self.avail.add(label)

    def get_new_label(self):
        """Return a new label, or None if we've run out."""
        try:
            label = self.avail.pop()
        except KeyError:
            return None
        self.inuse.add(label)
        return label

    @staticmethod
    def get_common_labels(labels):
        """Return list of common labels."""
        set_labels = [set(lab) for lab in labels]
        return set.intersection(*set_labels)

    @staticmethod
    def merge_labels(lab1, lab2):
        """Return the label representing both lab1 and lab2.

        Note the incoming labels could already be merged.
        """
        if lab1 == lab2:
            return lab1
        labs1 = set(list(lab1))
        labs2 = set(list(lab2))
        return ''.join(labs1.union(labs2))

    @staticmethod
    def unmerge_labels(prune, target):
        """Unmerge prune from target."""
        for char in list(prune):
            target = target.replace(char, '')
        return target

    @staticmethod
    def match_labels(lab1, lab2):
        """Return True if lab1 and lab2 have any labels in common.

        If they do, the owner tasks can be considered part of the same flow.
        Note the incoming labels could already be merged.
        """
        labs1 = set(list(lab1))
        labs2 = set(list(lab2))
        return bool(labs1.intersection(labs2))


class TaskPool:
    """Task pool of a workflow."""

    ERR_PREFIX_TASKID_MATCH = "No matching tasks found: "

    def __init__(
        self,
        config: 'WorkflowConfig',
        workflow_db_mgr: 'WorkflowDatabaseManager',
        task_events_mgr: 'TaskEventsManager',
        data_store_mgr: 'DataStoreMgr'
    ) -> None:

        self.config: 'WorkflowConfig' = config
        self.stop_point = config.final_point
        self.workflow_db_mgr: 'WorkflowDatabaseManager' = workflow_db_mgr
        self.task_events_mgr: 'TaskEventsManager' = task_events_mgr
        # TODO this is ugly:
        self.task_events_mgr.spawn_func = self.spawn_on_output
        self.data_store_mgr: 'DataStoreMgr' = data_store_mgr
        self.flow_label_mgr = FlowLabelMgr()

        self.do_reload = False
        self.custom_runahead_limit = self.config.get_custom_runahead_limit()
        self.max_future_offset: Optional['IntervalBase'] = None
        self._prev_runahead_base_point: Optional['PointBase'] = None
        self.max_num_active_cycle_points: int = (
            self.config.get_max_num_active_cycle_points())
        self._prev_runahead_sequence_points: Optional[List['PointBase']] = None

        self.main_pool: Pool = {}
        self.hidden_pool: Pool = {}
        self.main_pool_list: List[TaskProxy] = []
        self.hidden_pool_list: List[TaskProxy] = []
        self.main_pool_changed = False
        self.hidden_pool_changed = False

        self.hold_point: Optional['PointBase'] = None
        self.abs_outputs_done: Set[Tuple[str, str, str]] = set()

        self.stop_task_id: Optional[str] = None
        self.stop_task_finished = False
        self.abort_task_failed = False
        self.expected_failed_tasks = self.config.get_expected_failed_tasks()

        self.orphans: List[str] = []
        self.task_name_list = self.config.get_task_name_list()
        self.task_queue_mgr = IndepQueueManager(
            self.config.cfg['scheduling']['queues'],
            self.config.get_task_name_list(),
            self.config.runtime['descendants']
        )

    def set_stop_task(self, task_id):
        """Set stop after a task."""
        name = TaskID.split(task_id)[0]
        if name in self.config.get_task_name_list():
            task_id = TaskID.get_standardised_taskid(task_id)
            LOG.info("Setting stop task: " + task_id)
            self.stop_task_id = task_id
            self.stop_task_finished = False
            self.workflow_db_mgr.put_workflow_stop_task(task_id)
        else:
            LOG.warning("Requested stop task name does not exist: %s" % name)

    def stop_task_done(self):
        """Return True if stop task has succeeded."""
        if self.stop_task_id is not None and self.stop_task_finished:
            LOG.info("Stop task %s finished" % self.stop_task_id)
            self.stop_task_id = None
            self.stop_task_finished = False
            self.workflow_db_mgr.delete_workflow_stop_task()
            return True
        else:
            return False

    def _swap_out(self, itask):
        """Swap old task for new, during reload."""
        if itask.point in self.hidden_pool:
            if itask.identity in self.hidden_pool[itask.point]:
                self.hidden_pool[itask.point][itask.identity] = itask
                self.hidden_pool_changed = True
        elif itask.point in self.main_pool:
            if itask.identity in self.main_pool[itask.point]:
                self.main_pool[itask.point][itask.identity] = itask
                self.main_pool_changed = True

    def add_to_pool(self, itask, is_new=True):
        """Add a new task to the hidden or main pool.

        Tasks whose recurrences allow them to spawn beyond the workflow
        stop point are added to the pool in the held state, ready to be
        released if the workflow stop point is changed.

        """
        if itask.is_task_prereqs_not_done() and not itask.is_manual_submit:
            # Add to hidden pool if not satisfied.
            self.hidden_pool.setdefault(itask.point, dict())
            self.hidden_pool[itask.point][itask.identity] = itask
            self.hidden_pool_changed = True
        else:
            # Add to main pool.
            # First remove from hidden pool if necessary.
            try:
                del self.hidden_pool[itask.point][itask.identity]
            except KeyError:
                pass
            else:
                self.hidden_pool_changed = True
                if not self.hidden_pool[itask.point]:
                    del self.hidden_pool[itask.point]
            self.main_pool.setdefault(itask.point, dict())
            self.main_pool[itask.point][itask.identity] = itask
            self.main_pool_changed = True

            # Register pool node reference data-store with ID_DELIM format
            self.data_store_mgr.add_pool_node(itask.tdef.name, itask.point)
            # Create new data-store n-distance graph window about this task
            self.data_store_mgr.increment_graph_window(itask)
            self.data_store_mgr.delta_task_state(itask)
            self.data_store_mgr.delta_task_held(itask)
            self.data_store_mgr.delta_task_queued(itask)
            self.data_store_mgr.delta_task_runahead(itask)

        if is_new:
            # Add row to "task_states" table:
            self.workflow_db_mgr.put_insert_task_states(itask, {
                "time_created": get_current_time_string(),
                "time_updated": get_current_time_string(),
                "status": itask.state.status,
                "flow_label": itask.flow_label})
            # Add row to "task_outputs" table:
            if itask.state.outputs.has_custom_triggers():
                self.workflow_db_mgr.put_insert_task_outputs(itask)
        return itask

    def release_runahead_tasks(self):
        """Release runahead tasks.

        This serves to restrict the number of active cycle points.

        Compute runahead limit, and release tasks to the main pool if they are
        below that point (and <= the stop point, if there is a stop point).
        Return True if any tasks released, else False.

        """
        if not self.main_pool:
            # (At start-up, in case main pool doesn't exist yet)
            return False

        released = False

        # Any finished tasks can be released immediately (this can happen at
        # restart when all tasks are initially loaded into the runahead pool).
        # And any manually-triggered task.

        for itask in (
            itask
            for point_id_map in self.main_pool.values()
            for itask in point_id_map.values()
            if itask.state.is_runahead
            if itask.state(
                TASK_STATUS_FAILED,
                TASK_STATUS_SUCCEEDED,
                TASK_STATUS_EXPIRED
            )
            or itask.is_manual_submit
        ):
            self.release_runahead_task(itask)
            released = True

        points = []
        for point, itasks in sorted(self.get_tasks_by_point().items()):
            if points or any(
                not itask.state(
                    TASK_STATUS_FAILED,
                    TASK_STATUS_SUCCEEDED,
                    TASK_STATUS_EXPIRED
                )
                for itask in itasks
            ):
                points.append(point)

        if not points:
            return False

        # Get the earliest point with unfinished tasks.
        runahead_base_point = min(points)

        runahead_number_limit = None
        runahead_time_limit = None
        if isinstance(self.custom_runahead_limit, IntegerInterval):
            runahead_number_limit = int(self.custom_runahead_limit)
        elif isinstance(self.custom_runahead_limit, ISO8601Interval):
            runahead_time_limit = self.custom_runahead_limit

        # Get all cycling points possible after the runahead base point.
        if (self._prev_runahead_base_point is not None and
                runahead_base_point == self._prev_runahead_base_point):
            # Cache for speed.
            sequence_points = self._prev_runahead_sequence_points
        else:
            sequence_points = set()
            for sequence in self.config.sequences:
                seq_point = sequence.get_next_point(runahead_base_point)
                count = 1
                while seq_point is not None:
                    if runahead_time_limit is not None:
                        if seq_point > (runahead_base_point +
                                        runahead_time_limit):
                            break
                    else:
                        if count > runahead_number_limit:
                            break
                        count += 1
                    sequence_points.add(seq_point)
                    seq_point = sequence.get_next_point(seq_point)
            self._prev_runahead_sequence_points = sequence_points
            self._prev_runahead_base_point = runahead_base_point

        points = set(points).union(sequence_points)

        if runahead_number_limit is not None:
            # Calculate which tasks to release based on a maximum number of
            # active cycle points (active meaning non-finished tasks).
            latest_allowed_point = sorted(points)[:runahead_number_limit][-1]
            if self.max_future_offset is not None:
                # For the first N points, release their future trigger tasks.
                latest_allowed_point += self.max_future_offset
        else:
            # Calculate which tasks to release based on a maximum duration
            # measured from the oldest non-finished task.
            latest_allowed_point = runahead_base_point + runahead_time_limit

            if (self._prev_runahead_base_point is None or
                    self._prev_runahead_base_point != runahead_base_point):
                if runahead_time_limit < self.max_future_offset:
                    LOG.warning(
                        f'runahead limit "{runahead_time_limit}" '
                        'is less than future triggering offset '
                        f'"{self.max_future_offset}"; workflow may stall.')
            self._prev_runahead_base_point = runahead_base_point

        if self.stop_point and latest_allowed_point > self.stop_point:
            latest_allowed_point = self.stop_point

        # An intermediate list (release_me) is necessary here because
        # self.release_runahead_tasks() can change the task pool size
        # (parentless tasks are spawned when their previous instances are
        # released from runahead limiting).
        release_me = []
        for itask in (
            itask
            for point, itask_id_map in self.main_pool.items()
            for itask in itask_id_map.values()
            if point <= latest_allowed_point
            if itask.state.is_runahead
        ):
            release_me.append(itask)

        for itask in release_me:
            self.release_runahead_task(itask)
            released = True

        return released

    def load_abs_outputs_for_restart(self, row_idx, row):
        cycle, name, output = row
        self.abs_outputs_done.add((name, cycle, output))

    def load_db_task_pool_for_restart(self, row_idx, row):
        """Load tasks from DB task pool/states/jobs tables.

        Output completion status is loaded from the DB, and tasks recorded
        as submitted or running are polled to confirm their true status.
        Tasks are added to queues again on release from runahead pool.

        """
        if row_idx == 0:
            LOG.info("LOADING task proxies")
        # Create a task proxy corresponding to this DB entry.
        (cycle, name, flow_label, is_late, status, is_held, submit_num, _,
         platform_name, time_submit, time_run, timeout, outputs_str) = row
        try:
            itask = TaskProxy(
                self.config.get_taskdef(name),
                get_point(cycle),
                flow_label,
                is_held=is_held,
                submit_num=submit_num,
                is_late=bool(is_late))
        except WorkflowConfigError:
            LOG.exception(
                f'ignoring task {name} from the workflow run database\n'
                '(its task definition has probably been deleted).')
        except Exception:
            LOG.exception(f'could not load task {name}')
        else:
            if status in (
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING
            ):
                # update the task proxy with user@host
                itask.platform = get_platform(platform_name)

                if time_submit:
                    itask.set_summary_time('submitted', time_submit)
                if time_run:
                    itask.set_summary_time('started', time_run)
                if timeout is not None:
                    itask.timeout = timeout
            elif status == TASK_STATUS_PREPARING:
                # put back to be readied again.
                status = TASK_STATUS_WAITING

            # Running or finished task can have completed custom outputs.
            if itask.state(
                    TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED,
                    TASK_STATUS_SUCCEEDED
            ):
                for message in json.loads(outputs_str).values():
                    itask.state.outputs.set_completion(message, True)
                    self.data_store_mgr.delta_task_output(itask, message)

            if platform_name:
                itask.summary['platforms_used'][
                    int(submit_num)] = platform_name
            LOG.info(
                f"+ {name}.{cycle} {status}{' (held)' if is_held else ''}")

            # Update prerequisite satisfaction status from DB
            sat = {}
            for prereq_name, prereq_cycle, prereq_output, satisfied in (
                    self.workflow_db_mgr.pri_dao.select_task_prerequisites(
                        cycle, name)):
                key = (prereq_name, prereq_cycle, prereq_output)
                sat[key] = satisfied if satisfied != '0' else False

            for itask_prereq in itask.state.prerequisites:
                for key, _ in itask_prereq.satisfied.items():
                    itask_prereq.satisfied[key] = sat[key]

            itask.state.reset(status)
            itask.state.reset(is_runahead=True)
            self.add_to_pool(itask, is_new=False)

    def load_db_task_action_timers(self, row_idx, row):
        """Load a task action timer, e.g. event handlers, retry states."""
        if row_idx == 0:
            LOG.info("LOADING task action timers")
        (cycle, name, ctx_key_raw, ctx_raw, delays_raw, num, delay,
         timeout) = row
        id_ = TaskID.get(name, cycle)
        try:
            # Extract type namedtuple variables from JSON strings
            ctx_key = json.loads(str(ctx_key_raw))
            ctx_data = json.loads(str(ctx_raw))
            for known_cls in [
                    CustomTaskEventHandlerContext,
                    TaskEventMailContext,
                    TaskJobLogsRetrieveContext]:
                if ctx_data and ctx_data[0] == known_cls.__name__:
                    ctx = known_cls(*ctx_data[1])
                    break
            else:
                ctx = ctx_data
                if ctx is not None:
                    ctx = tuple(ctx)
            delays = json.loads(str(delays_raw))
        except ValueError:
            LOG.exception(
                "%(id)s: skip action timer %(ctx_key)s" %
                {"id": id_, "ctx_key": ctx_key_raw})
            return
        LOG.info("+ %s.%s %s" % (name, cycle, ctx_key))
        if ctx_key == "poll_timer":
            itask = self._get_task_by_id(id_)
            if itask is None:
                LOG.warning("%(id)s: task not found, skip" % {"id": id_})
                return
            itask.poll_timer = TaskActionTimer(
                ctx, delays, num, delay, timeout)
        elif ctx_key[0] == "try_timers":
            itask = self._get_task_by_id(id_)
            if itask is None:
                LOG.warning("%(id)s: task not found, skip" % {"id": id_})
                return
            if 'retrying' in ctx_key[1]:
                if 'submit' in ctx_key[1]:
                    submit = True
                    ctx_key[1] = TimerFlags.SUBMISSION_RETRY
                else:
                    submit = False
                    ctx_key[1] = TimerFlags.EXECUTION_RETRY

                if timeout:
                    LOG.info(
                        f'  (upgrading retrying state for {itask.identity})')
                    self.task_events_mgr._retry_task(
                        itask,
                        float(timeout),
                        submit_retry=submit
                    )
            itask.try_timers[ctx_key[1]] = TaskActionTimer(
                ctx, delays, num, delay, timeout)
        elif ctx:
            key1, submit_num = ctx_key
            # Convert key1 to type tuple - JSON restores as type list
            # and this will not previously have been converted back
            if isinstance(key1, list):
                key1 = tuple(key1)
            key = (key1, cycle, name, submit_num)
            self.task_events_mgr.add_event_timer(
                key,
                TaskActionTimer(
                    ctx, delays, num, delay, timeout
                )
            )
        else:
            LOG.exception(
                "%(id)s: skip action timer %(ctx_key)s" %
                {"id": id_, "ctx_key": ctx_key_raw})
            return

    def release_runahead_task(self, itask: TaskProxy) -> None:
        """Release itask from runahead limiting.

        Also auto-spawn next instance if:
        - no parents to do it
        - has absolute triggers (these are satisfied already by definition)
        """
        if itask.state.reset(is_runahead=False):
            self.data_store_mgr.delta_task_runahead(itask)

        LOG.info("[%s] -released from runahead", itask)

        # Queue if ready to run
        if all(itask.is_ready_to_run()):
            # (otherwise waiting on xtriggers etc.)
            self.queue_tasks([itask])

        if itask.tdef.max_future_prereq_offset is not None:
            self.set_max_future_offset()
        if itask.tdef.sequential:
            # implicit prev-instance parent
            return
        if not itask.reflow:
            return
        next_point = itask.next_point()
        if next_point is not None:
            parent_points = itask.tdef.get_parent_points(next_point)
            n_task = None
            if (not parent_points or
                    all(x < self.config.start_point for x in parent_points)):
                # Auto-spawn next instance of tasks with no parents at the next
                # point (or with all parents before the workflow start point).
                n_task = self.get_or_spawn_task(
                    itask.tdef.name, next_point, flow_label=itask.flow_label,
                    parent_id=itask.identity)
            elif itask.tdef.get_abs_triggers(next_point):
                # Auto-spawn (if needed) next absolute-triggered instances.
                n_task = self.get_or_spawn_task(
                    itask.tdef.name, next_point,
                    flow_label=itask.flow_label,
                    parent_id=itask.identity)
            if n_task:
                self.add_to_pool(n_task)

    def remove(self, itask, reason=""):
        """Remove a task from the pool (e.g. after a reload)."""
        msg = "task proxy removed"
        if reason:
            msg += " (%s)" % reason

        try:
            del self.hidden_pool[itask.point][itask.identity]
        except KeyError:
            pass
        else:
            # e.g. for suicide?
            self.hidden_pool_changed = True
            if not self.hidden_pool[itask.point]:
                del self.hidden_pool[itask.point]
            return

        try:
            del self.main_pool[itask.point][itask.identity]
        except KeyError:
            pass
        else:
            self.main_pool_changed = True
            if not self.main_pool[itask.point]:
                del self.main_pool[itask.point]
                self.task_queue_mgr.remove_task(itask)
                if itask.tdef.max_future_prereq_offset is not None:
                    self.set_max_future_offset()

            # Notify the data-store manager of their removal
            # (the manager uses window boundary tracking for pruning).
            self.data_store_mgr.remove_pool_node(itask.tdef.name, itask.point)
            # Event-driven final update of task_states table.
            # TODO: same for datastore (still updated by scheduler loop)
            self.workflow_db_mgr.put_update_task_state(itask)
            LOG.debug("[%s] -%s", itask, msg)
            del itask

    def get_all_tasks(self) -> List[TaskProxy]:
        """Return a list of all task proxies."""
        return self.get_hidden_tasks() + self.get_tasks()

    def get_tasks(self) -> List[TaskProxy]:
        """Return a list of task proxies in the main pool."""
        if self.main_pool_changed:
            self.main_pool_changed = False
            self.main_pool_list = []
            for _, itask_id_map in self.main_pool.items():
                for __, itask in itask_id_map.items():
                    self.main_pool_list.append(itask)
        return self.main_pool_list

    def get_hidden_tasks(self) -> List[TaskProxy]:
        """Return a list of task proxies in the hidden pool."""
        if self.hidden_pool_changed:
            self.hidden_pool_changed = False
            self.hidden_pool_list = []
            for itask_id_maps in self.hidden_pool.values():
                self.hidden_pool_list.extend(list(itask_id_maps.values()))
        return self.hidden_pool_list

    def get_tasks_by_point(self):
        """Return a map of task proxies by cycle point."""
        point_itasks = {}
        for point, itask_id_map in self.main_pool.items():
            point_itasks[point] = list(itask_id_map.values())
        for point, itask_id_map in self.hidden_pool.items():
            if point not in point_itasks:
                point_itasks[point] = list(itask_id_map.values())
            else:
                point_itasks[point] += list(itask_id_map.values())

        return point_itasks

    def _get_hidden_task_by_id(self, id_):
        """Return runahead pool task by ID if it exists, or None."""
        for itask_ids in list(self.hidden_pool.values()):
            try:
                return itask_ids[id_]
            except KeyError:
                pass

    def _get_task_by_id(self, id_):
        """Return main pool task by ID if it exists, or None."""
        for itask_ids in list(self.main_pool.values()):
            try:
                return itask_ids[id_]
            except KeyError:
                pass

    def queue_tasks(self, itasks):
        """Queue tasks that are ready to run."""
        for itask in itasks:
            itask.state.reset(is_queued=True)
            self.data_store_mgr.delta_task_queued(itask)
        self.task_queue_mgr.push_tasks(itasks)

    def release_queued_tasks(self):
        """Return list of queue-released tasks for job prep."""
        released = self.task_queue_mgr.release_tasks(
            Counter(
                [
                    t.tdef.name for t in self.get_tasks()
                    if t.state(TASK_STATUS_PREPARING,
                               TASK_STATUS_SUBMITTED,
                               TASK_STATUS_RUNNING)
                ]
            )
        )
        for itask in released:
            itask.state.reset(is_queued=False)
            itask.state.reset(TASK_STATUS_PREPARING)
            itask.waiting_on_job_prep = True
            self.data_store_mgr.delta_task_state(itask)
            self.data_store_mgr.delta_task_queued(itask)
            LOG.info(f"Queue released: {itask.identity}")
        return released

    def get_min_point(self):
        """Return the minimum cycle point currently in the pool."""
        cycles = list(self.main_pool)
        minc = None
        if cycles:
            minc = min(cycles)
        return minc

    def set_max_future_offset(self):
        """Calculate the latest required future trigger offset."""
        max_offset = None
        for itask in self.get_tasks():
            if (itask.tdef.max_future_prereq_offset is not None and
                    (max_offset is None or
                     itask.tdef.max_future_prereq_offset > max_offset)):
                max_offset = itask.tdef.max_future_prereq_offset
        self.max_future_offset = max_offset

    def set_do_reload(self, config):
        """Set the task pool to reload mode."""
        self.config = config
        if config.options.stopcp:
            self.stop_point = get_point(config.options.stopcp)
        else:
            self.stop_point = config.final_point
        self.do_reload = True

        self.custom_runahead_limit = self.config.get_custom_runahead_limit()
        self.max_num_active_cycle_points = (
            self.config.get_max_num_active_cycle_points())

        # find any old tasks that have been removed from the workflow
        old_task_name_list = self.task_name_list
        self.task_name_list = self.config.get_task_name_list()
        for name in old_task_name_list:
            if name not in self.task_name_list:
                self.orphans.append(name)
        for name in self.task_name_list:
            if name in self.orphans:
                self.orphans.remove(name)
        # adjust the new workflow config to handle the orphans
        self.config.adopt_orphans(self.orphans)

    def reload_taskdefs(self):
        """Reload the definitions of task proxies in the pool.

        Orphaned tasks (whose definitions were removed from the workflow):
        - remove if not active yet
        - if active, leave them but prevent them from spawning children on
          subsequent outputs
        Otherwise: replace task definitions but copy over existing outputs etc.

        TODO: document for users: beware of reloading graph changes that affect
        current active tasks. Such tasks are active with their original defns -
        including what children they spawn - and it is not possible in general
        to be sure that new defns are compatible with already-active old tasks.
        So active tasks attempt to spawn the children that their (pre-reload)
        defns say they should.

        """
        LOG.info("Reloading task definitions.")
        tasks = self.get_all_tasks()
        # Log tasks orphaned by a reload but not currently in the task pool.
        for name in self.orphans:
            if name not in (itask.tdef.name for itask in tasks):
                LOG.warning("Removed task: '%s'", name)
        for itask in tasks:
            if itask.tdef.name in self.orphans:
                if (
                        itask.state(TASK_STATUS_WAITING)
                        or itask.state.is_held
                        or itask.state.is_queued
                ):
                    # Remove orphaned task if it hasn't started running yet.
                    self.remove(itask, 'task definition removed')
                else:
                    # Keep active orphaned task, but stop it from spawning.
                    itask.graph_children = {}
                    LOG.warning("[%s] -will not spawn children"
                                " (task definition removed)", itask)
            else:
                new_task = TaskProxy(
                    self.config.get_taskdef(itask.tdef.name),
                    itask.point,
                    itask.flow_label, itask.state.status)
                itask.copy_to_reload_successor(new_task)
                self._swap_out(new_task)
                LOG.info('[%s] -reloaded task definition', itask)
                if itask.state(*TASK_STATUSES_ACTIVE):
                    LOG.warning(
                        "[%s] -job(%02d) active with pre-reload settings",
                        itask,
                        itask.submit_num)

        # Reassign live tasks to the internal queue
        del self.task_queue_mgr
        self.task_queue_mgr = IndepQueueManager(
            self.config.cfg['scheduling']['queues'],
            self.config.get_task_name_list(),
            self.config.runtime['descendants']
        )

        # Now queue all tasks that are ready to run
        to_queue = []
        for itask in self.get_tasks():
            if itask.state.is_queued:
                # Already queued
                continue
            ready_check_items = itask.is_ready_to_run()
            # Use this periodic checking point for data-store delta
            # creation, some items aren't event driven (i.e. clock).
            if itask.tdef.clocktrigger_offset is not None:
                self.data_store_mgr.delta_task_clock_trigger(
                    itask, ready_check_items)

            if all(ready_check_items) and not itask.state.is_runahead:
                to_queue.append(itask)
        self.queue_tasks(to_queue)

        LOG.info("Reload completed.")
        self.do_reload = False

    def set_stop_point(self, stop_point):
        """Set the global workflow stop point."""
        if self.stop_point == stop_point:
            return
        LOG.info("Setting stop cycle point: %s", stop_point)
        self.stop_point = stop_point
        for itask in self.get_tasks():
            # check cycle stop or hold conditions
            if (
                    self.stop_point
                    and itask.point > self.stop_point
                    and itask.state(
                        TASK_STATUS_WAITING,
                        is_queued=True,
                        is_held=False
                    )
            ):
                LOG.warning(
                    "[%s] -not running (beyond workflow stop cycle) %s",
                    itask,
                    self.stop_point)
                if itask.state.reset(is_held=True):
                    self.data_store_mgr.delta_task_held(itask)
        return self.stop_point

    def can_stop(self, stop_mode):
        """Return True if workflow can stop.

        A task is considered active if:
        * It is in the active state and not marked with a kill failure.
        * It has pending event handlers.
        """
        if stop_mode is None:
            return False
        if stop_mode == StopMode.REQUEST_NOW_NOW:
            return True
        if self.task_events_mgr._event_timers:
            return False
        for itask in self.get_tasks():
            if (
                    stop_mode == StopMode.REQUEST_CLEAN
                    and itask.state(*TASK_STATUSES_ACTIVE)
                    and not itask.state.kill_failed
            ):
                return False
        return True

    def warn_stop_orphans(self):
        """Log (warning) orphaned tasks on workflow stop."""
        orphans = []
        orphans_kill_failed = []
        for itask in self.get_tasks():
            if itask.state(*TASK_STATUSES_ACTIVE):
                if itask.state.kill_failed:
                    orphans_kill_failed.append(itask)
                else:
                    orphans.append(itask)
        if orphans_kill_failed:
            LOG.warning(
                "Orphaned task jobs (kill failed):\n"
                + "\n".join(
                    f"* {itask.identity} ({itask.state.status})"
                    for itask in orphans_kill_failed
                )
            )
        if orphans:
            LOG.warning(
                "Orphaned task jobs:\n"
                + "\n".join(
                    f"* {itask.identity} ({itask.state.status})"
                    for itask in orphans
                )
            )

        for key1, point, name, submit_num in (
                self.task_events_mgr._event_timers
        ):
            LOG.warning("%s/%s/%s: incomplete task event handler %s" % (
                point, name, submit_num, key1))

    def is_stalled(self):
        """Return True if the workflow is stalled.

        A workflow is stalled if it is not held and the active pool contains
        only unhandled failed tasks and un-released runahead tasks.

        """
        self.release_runahead_tasks()
        unhandled_failed = []
        for itask in self.get_tasks():
            if itask.state(*TASK_STATUSES_FAILURE):
                unhandled_failed.append(itask)
            elif itask.state.is_runahead:
                continue
            else:
                return False
        if unhandled_failed:
            LOG.warning(
                "Workflow stalled with unhandled failed tasks:\n"
                + "\n".join(
                    f"* {itask.identity} ({itask.state.status})"
                    for itask in unhandled_failed
                )
            )
            return True
        else:
            return False

    def report_unmet_deps(self):
        """Log unmet dependencies on stall or shutdown."""
        prereqs_map = {}
        for itask in self.get_hidden_tasks():
            prereqs_map[itask.identity] = []
            for prereq_str, is_met in itask.state.prerequisites_dump():
                if not is_met:
                    prereqs_map[itask.identity].append(prereq_str)

        # prune tree to ignore items that are elsewhere in it
        for id_, prereqs in list(prereqs_map.copy().items()):
            if not prereqs:
                # (tasks in runahead pool that are not unsatisfied)
                del prereqs_map[id_]
                continue
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

        if prereqs_map:
            LOG.warning(
                "Some partially satisfied prerequisites left over:\n"
                + "\n".join(
                    f"{id_} is waiting on:"
                    + "\n".join(
                        f"\n* {prereq}" for prereq in prereqs
                    ) for id_, prereqs in prereqs_map.items()
                )
            )

    def set_hold_point(self, point: 'PointBase') -> None:
        """Set the point after which all tasks must be held."""
        self.hold_point = point
        for itask in self.get_all_tasks():
            if itask.point > point:
                if itask.state.reset(is_held=True):
                    self.data_store_mgr.delta_task_held(itask)
        self.workflow_db_mgr.put_workflow_hold_cycle_point(point)

    def hold_tasks(self, items: Iterable[str]) -> int:
        """Hold tasks with IDs matching the specified items."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            if itask.state.reset(is_held=True):
                self.data_store_mgr.delta_task_held(itask)
        return len(bad_items)

    def release_held_tasks(self, items: Iterable[str]) -> int:
        """Release held tasks with IDs matching any specified items."""
        itasks, bad_items = self.filter_task_proxies(items)
        to_queue = []
        for itask in itasks:
            if itask.state.reset(is_held=False):
                self.data_store_mgr.delta_task_held(itask)
                if (
                        all(itask.is_ready_to_run())
                        and not itask.state.is_runahead
                ):
                    to_queue.append(itask)
        self.queue_tasks(to_queue)
        return len(bad_items)

    def release_hold_point(self) -> None:
        """Release all tasks and unset the workflow hold point."""
        self.hold_point = None
        to_queue = []
        for itask in self.get_all_tasks():
            if itask.state.reset(is_held=False):
                self.data_store_mgr.delta_task_held(itask)
                if (
                        all(itask.is_ready_to_run())
                        and not itask.state.is_runahead
                ):
                    to_queue.append(itask)
        self.queue_tasks(to_queue)
        self.workflow_db_mgr.delete_workflow_hold_cycle_point()

    def check_abort_on_task_fails(self):
        """Check whether workflow should abort on task failure.

        Return True if a task failed and `--abort-if-any-task-fails` was given.
        """
        return self.abort_task_failed

    def spawn_on_output(self, itask, output):
        """Spawn and update children, remove parent if finished.

        Also set a the abort-on-task-failed flag if necessary.
        If not itask.reflow update existing children but don't spawn them.

        If an absolute output is completed update the store of completed abs
        outputs, and update the prerequisites of every instance of the child
        in the pool. (And in self.spawn() use the store of completed abs
        outputs to satisfy any tasks with abs prerequisites).

        """
        if output == TASK_OUTPUT_FAILED:
            if (self.expected_failed_tasks is not None
                    and itask.identity not in self.expected_failed_tasks):
                self.abort_task_failed = True

        try:
            children = itask.graph_children[output]
        except KeyError:
            # No children depend on this output
            children = []

        suicide = []
        for c_name, c_point, is_abs in children:
            if is_abs:
                self.abs_outputs_done.add((itask.tdef.name,
                                          str(itask.point), output))
                self.workflow_db_mgr.put_insert_abs_output(
                    str(itask.point), itask.tdef.name, output)
                self.workflow_db_mgr.process_queued_ops()
            if itask.reflow:
                c_task = self.get_or_spawn_task(
                    c_name, c_point, flow_label=itask.flow_label,
                    parent_id=itask.identity)
            else:
                # Don't spawn, but update existing children.
                c_task = self.get_task(c_name, c_point)

            if c_task is not None:
                # Update downstream prerequisites directly.
                if is_abs:
                    tasks, _ = self.filter_task_proxies([c_name])
                else:
                    tasks = [c_task]
                for t in tasks:
                    t.state.satisfy_me(
                        set([(itask.tdef.name, str(itask.point), output)]))
                    self.data_store_mgr.delta_task_prerequisite(t)
                # Event-driven suicide.
                if (c_task.state.suicide_prerequisites and
                        c_task.state.suicide_prerequisites_all_satisfied()):
                    suicide.append(c_task)
                # Add child to the task pool, if not already there.
                self.add_to_pool(c_task)

        for c_task in suicide:
            if c_task.state(
                    TASK_STATUS_PREPARING,
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING,
                    is_held=False):
                LOG.warning(f'[{c_task}] -suiciding while active')
            self.remove(c_task, 'SUICIDE')

        # Remove the parent task if finished.
        if (output in [TASK_OUTPUT_SUCCEEDED, TASK_OUTPUT_EXPIRED]
                or output == TASK_OUTPUT_FAILED and itask.failure_handled):
            if itask.identity == self.stop_task_id:
                self.stop_task_finished = True
            self.remove(itask, 'finished')

    def get_or_spawn_task(self, name, point, flow_label=None, reflow=True,
                          parent_id=None):
        """Return existing or spawned task, or None."""
        return (self.get_task(name, point, flow_label)
                or self.spawn_task(name, point, flow_label, reflow, parent_id))

    def _merge_flow_labels(self, itask, flab2):
        """Merge flab2 into itask's flow label and update DB."""

        # TODO can we do a more minimal (flow-label only) update of the
        # existing row? (flow label is a primary key so need new insert).
        # ? self.workflow_db_mgr.put_update_task_state(itask)

        if flab2 is None or flab2 == itask.flow_label:
            return
        itask.flow_label = self.flow_label_mgr.merge_labels(
            itask.flow_label, flab2)
        self.workflow_db_mgr.put_insert_task_states(itask, {
            "status": itask.state.status,
            "flow_label": itask.flow_label})
        self.workflow_db_mgr.process_queued_ops()  # TODO is this needed here?
        LOG.info('%s merged flow(%s)', itask.identity, itask.flow_label)

    def get_task_main(self, name, point, flow_label=None):
        """Return task proxy from main pool and merge flow label if found."""
        itask = self._get_task_by_id(TaskID.get(name, point))
        if itask is not None:
            self._merge_flow_labels(itask, flow_label)
        return itask

    def get_task(self, name, point, flow_label=None):
        """Return existing task proxy and merge flow label if found."""
        itask = (
            self._get_hidden_task_by_id(TaskID.get(name, point))
            or self._get_task_by_id(TaskID.get(name, point))
        )
        if itask is None:
            LOG.debug('Task %s.%s not found in task pool.', name, point)
            return None
        self._merge_flow_labels(itask, flow_label)
        return itask

    def can_spawn(self, name: str, point: 'PointBase') -> bool:
        """Return True if name.point is within various workflow limits."""

        if name not in self.config.get_task_name_list():
            LOG.debug('No task definition %s', name)
            return False

        # Don't spawn outside of graph limits.
        # TODO: is it possible for initial_point to not be defined??
        # (see also the similar check + log message in scheduler.py)
        if self.config.initial_point and point < self.config.initial_point:
            # Attempted manual trigger prior to FCP
            # or future triggers like foo[+P1] => bar, with foo at ICP.
            LOG.debug(
                'Not spawning %s.%s: before initial cycle point', name, point)
            return False
        elif self.config.final_point and point > self.config.final_point:
            # Only happens on manual trigger beyond FCP
            LOG.debug(
                'Not spawning %s.%s: beyond final cycle point', name, point)
            return False

        return True

    def spawn_task(
        self,
        name: str,
        point: 'PointBase',
        flow_label: Optional[str] = None,
        reflow: bool = True,
        parent_id: Optional[str] = None
    ) -> Optional[TaskProxy]:
        """Spawn name.point and add to runahead pool. Return it, or None."""
        if not self.can_spawn(name, point):
            return None

        # Get submit number by flow label {flow_label: submit_num, ...}
        snums = self.workflow_db_mgr.pri_dao.select_submit_nums(
            name, str(point)
        )
        try:
            submit_num = max(snums.values())
        except ValueError:
            # Task never spawned in any flow.
            submit_num = 0

        for f_id in snums.keys():
            # Flow labels of previous instances.  E.g. f_id "u".
            if self.flow_label_mgr.match_labels(flow_label, f_id):
                # Already spawned in this flow. E.g. flow_label "uV".
                # TODO update existing DB row to avoid cond reflow from V too?
                LOG.warning('Not spawning %s.%s (spawned in flow %s)',
                            name, point, f_id)
                return None

        # Spawn if on-sequence and within recurrence bounds.
        taskdef = self.config.get_taskdef(name)
        if not taskdef.is_valid_point(point):
            return None

        itask = TaskProxy(
            taskdef,
            point, flow_label,
            submit_num=submit_num, reflow=reflow)
        if self.hold_point and itask.point > self.hold_point:
            # Hold if beyond the workflow hold point
            LOG.info("[%s] -holding (beyond workflow hold point) %s",
                     itask, self.hold_point)
            if itask.state.reset(is_held=True):
                self.data_store_mgr.delta_task_held(itask)
        if self.stop_point and itask.point <= self.stop_point:
            future_trigger_overrun = False
            for pct in itask.state.prerequisites_get_target_points():
                if pct > self.stop_point:
                    future_trigger_overrun = True
                    break
            if future_trigger_overrun:
                LOG.warning("[%s] -won't run: depends on a "
                            "task beyond the stop point", itask)

        # Attempt to satisfy any absolute triggers now.
        # TODO: consider doing this only for tasks with absolute prerequisites.
        if itask.state.prerequisites_are_not_all_satisfied():
            itask.state.satisfy_me(self.abs_outputs_done)

        if parent_id is not None:
            msg = "(" + parent_id + ") spawned %s.%s flow(%s)"
        else:
            msg = "(no parent) spawned %s.%s %s"
        if flow_label is None:
            # Manual trigger: new flow
            msg += " (new flow)"

        LOG.info(msg, name, point, flow_label)
        return itask

    def match_taskdefs(self, items):
        """Return matching taskdefs valid for selected cycle points."""
        n_warnings = 0
        task_items = {}
        for item in items:
            point_str, name_str = self._parse_task_item(item)[:2]
            if point_str is None:
                LOG.warning(
                    "%s: task to spawn must have a cycle point" % (item))
                n_warnings += 1
                continue
            try:
                point_str = standardise_point_string(point_str)
            except PointParsingError as exc:
                LOG.warning(
                    self.ERR_PREFIX_TASKID_MATCH + ("%s (%s)" % (item, exc)))
                n_warnings += 1
                continue
            taskdefs = self.config.find_taskdefs(name_str)
            if not taskdefs:
                LOG.warning(self.ERR_PREFIX_TASKID_MATCH + item)
                n_warnings += 1
                continue
            point = get_point(point_str)
            for taskdef in taskdefs:
                if taskdef.is_valid_point(point):
                    task_items[(taskdef.name, point)] = taskdef
        return n_warnings, task_items

    def force_spawn_children(self, items, outputs):
        """Spawn downstream children of given task outputs on user command."""
        n_warnings, task_items = self.match_taskdefs(items)
        for (_, point), taskdef in sorted(task_items.items()):
            # This the upstream target task:
            itask = TaskProxy(taskdef, point,
                              self.flow_label_mgr.get_new_label())
            # Spawn downstream on selected outputs.
            for trig, out, _ in itask.state.outputs.get_all():
                if trig in outputs:
                    LOG.info('Forced spawning on %s:%s', itask.identity, out)
                    self.spawn_on_output(itask, out)

    def remove_tasks(self, items):
        """Remove tasks from the pool."""
        itasks, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            self.remove(itask, 'request')
        return len(bad_items)

    def force_trigger_tasks(self, items, reflow=False):
        """Trigger matching tasks, with or without reflow.

        Queue the task if not queued, otherwise release it to run.
        """
        # TODO check reflow from existing tasks - unless unhandled fail?
        n_warnings, task_items = self.match_taskdefs(items)
        flow_label = self.flow_label_mgr.get_new_label()
        for name, point in task_items.keys():
            itask = self.get_task_main(name, point, flow_label)
            if itask is not None:
                # Already in pool: trigger and merge flow labels.
                itask.is_manual_submit = True
                itask.reset_try_timers()
                # (If None, spawner reports cycle bounds errors).
                if itask.state.reset(TASK_STATUS_WAITING):
                    self.data_store_mgr.delta_task_state(itask)
                # (No need to set prerequisites satisfied here).
                if not itask.state.is_queued:
                    LOG.info("Force-trigger: queueing {itask.identity}")
                    self.queue_tasks([itask])
                else:
                    self.task_queue_mgr.force_release_task(itask)
            else:
                # Spawn with new flow label.
                itask = self.spawn_task(
                    name, point, flow_label, reflow=reflow)
                itask.is_manual_submit = True
                # This will queue the task.
                self.add_to_pool(itask, is_new=True)
                LOG.critical(f"WTF 2: {itask.identity}")
        return n_warnings

    def sim_time_check(self, message_queue):
        """Simulation mode: simulate task run times and set states."""
        if not self.config.run_mode('simulation'):
            return False
        sim_task_state_changed = False
        now = time()
        for itask in self.get_tasks():
            if itask.state.status != TASK_STATUS_RUNNING:
                continue
            # Started time is not set on restart
            if itask.summary['started_time'] is None:
                itask.summary['started_time'] = now
            timeout = (itask.summary['started_time'] +
                       itask.tdef.rtconfig['job']['simulated run length'])
            if now > timeout:
                conf = itask.tdef.rtconfig['simulation']
                job_d = get_task_job_id(
                    itask.point, itask.tdef.name, itask.submit_num)
                now_str = get_current_time_string()
                if (itask.point in conf['fail cycle points'] and
                        (itask.get_try_num() == 1 or
                         not conf['fail try 1 only'])):
                    message_queue.put(
                        (job_d, now_str, 'CRITICAL', TASK_STATUS_FAILED))
                else:
                    # Simulate message outputs.
                    for msg in itask.tdef.rtconfig['outputs'].values():
                        message_queue.put((job_d, now_str, 'INFO', msg))
                    message_queue.put(
                        (job_d, now_str, 'INFO', TASK_STATUS_SUCCEEDED))
                sim_task_state_changed = True
        return sim_task_state_changed

    def set_expired_tasks(self):
        res = False
        for itask in self.get_tasks():
            if self._set_expired_task(itask):
                res = True
        return res

    def _set_expired_task(self, itask):
        """Check if task has expired. Set state and event handler if so.

        Return True if task has expired.
        """
        if (
                not itask.state(
                    TASK_STATUS_WAITING,
                    is_held=False
                )
                or itask.tdef.expiration_offset is None
        ):
            return False
        if itask.expire_time is None:
            itask.expire_time = (
                itask.get_point_as_seconds() +
                itask.get_offset_as_seconds(itask.tdef.expiration_offset))
        if time() > itask.expire_time:
            msg = 'Task expired (skipping job).'
            LOG.warning('[%s] -%s', itask, msg)
            self.task_events_mgr.setup_event_handlers(itask, "expired", msg)
            # TODO succeeded and expired states are useless due to immediate
            # removal under all circumstances (unhandled failed is still used).
            if itask.state.reset(TASK_STATUS_EXPIRED, is_held=False):
                self.data_store_mgr.delta_task_state(itask)
                self.data_store_mgr.delta_task_held(itask)
            self.remove(itask, 'expired')
            return True
        return False

    def task_succeeded(self, id_):
        """Return True if task with id_ is in the succeeded state."""
        for itask in self.get_tasks():
            if (
                    itask.identity == id_
                    and itask.state(TASK_STATUS_SUCCEEDED)
            ):
                return True
        return False

    def filter_task_proxies(
        self, items: Iterable[str]
    ) -> Tuple[List[TaskProxy], List[str]]:
        """Return task proxies that match names, points, states in items.

        Args:
            items: strings for matching task proxies, each with the
            general form name[.point][:state] or [point/]name[:state]
            where name is a glob-like pattern for matching a task name or
            a family name.

        Return (itasks, bad_items).
        """
        itasks: List[TaskProxy] = []
        bad_items: List[str] = []
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
                    except PointParsingError:
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

    def stop_flow(self, flow_label):
        """Stop a particular flow from spawning any further."""
        # Stop tasks belong to flow_label from continuing.
        for itask in self.get_all_tasks():
            # Don't use match_label(); we don't want to stop merged flows.
            if itask.flow_label == flow_label:
                itask.reflow = False

    def prune_flow_labels(self):
        """Remove redundant flow labels.

        Note this iterates the task pool twice but it can be called
        infrequently and doesn't do anything if there is only one flow.

        """
        if self.flow_label_mgr.get_num_inuse() == 1:
            # Nothing to do.
            return
        # Gather all current labels.
        labels = [itask.flow_label for itask in self.get_all_tasks()]
        if not labels:
            return
        # Find any labels common to all tasks.
        common = self.flow_label_mgr.get_common_labels(labels)
        # And prune them back to just one.
        num = len(list(common))
        if num <= 1:
            return
        LOG.debug('Pruning redundant flow labels: %s', common)
        to_prune = []
        while num > 1:
            to_prune.append(common.pop())
            num -= 1
        for itask in self.get_all_tasks():
            itask.flow_label = self.flow_label_mgr.unmerge_labels(
                to_prune, itask.flow_label)
        self.flow_label_mgr.make_avail(to_prune)

    @staticmethod
    def _parse_task_item(
        item: str
    ) -> Tuple[Optional[str], str, Optional[str]]:
        """Parse point/name:state or name.point:state syntax."""
        point_str: Optional[str]
        name_str: str
        state_str: Optional[str]
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
