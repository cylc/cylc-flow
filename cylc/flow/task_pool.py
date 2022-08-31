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

from contextlib import suppress
from collections import Counter
import json
from time import time
from typing import Dict, Iterable, List, Optional, Set, TYPE_CHECKING, Tuple
import logging

import cylc.flow.flags
from cylc.flow import LOG
from cylc.flow.cycling.loader import get_point, standardise_point_string
from cylc.flow.exceptions import WorkflowConfigError, PointParsingError
from cylc.flow.id import Tokens, detokenise
from cylc.flow.id_cli import contains_fnmatch
from cylc.flow.id_match import filter_ids
from cylc.flow.workflow_status import StopMode
from cylc.flow.task_action_timer import TaskActionTimer, TimerFlags
from cylc.flow.task_events_mgr import (
    CustomTaskEventHandlerContext, TaskEventMailContext,
    TaskJobLogsRetrieveContext)
from cylc.flow.task_id import TaskID
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_state import (
    TASK_STATUSES_ACTIVE,
    TASK_STATUSES_FINAL,
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
from cylc.flow.util import (
    serialise,
    deserialise
)
from cylc.flow.wallclock import get_current_time_string
from cylc.flow.platforms import get_platform
from cylc.flow.task_queues.independent import IndepQueueManager

from cylc.flow.flow_mgr import FLOW_ALL, FLOW_NONE, FLOW_NEW

if TYPE_CHECKING:
    from cylc.flow.config import WorkflowConfig
    from cylc.flow.cycling import IntervalBase, PointBase
    from cylc.flow.data_store_mgr import DataStoreMgr
    from cylc.flow.taskdef import TaskDef
    from cylc.flow.task_events_mgr import TaskEventsManager
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
    from cylc.flow.flow_mgr import FlowMgr, FlowNums

Pool = Dict['PointBase', Dict[str, TaskProxy]]


class TaskPool:
    """Task pool of a workflow."""

    ERR_TMPL_NO_TASKID_MATCH = "No matching tasks found: {0}"
    ERR_PREFIX_TASK_NOT_ON_SEQUENCE = "Invalid cycle point for task: {0}, {1}"
    SUICIDE_MSG = "suicide"

    def __init__(
        self,
        config: 'WorkflowConfig',
        workflow_db_mgr: 'WorkflowDatabaseManager',
        task_events_mgr: 'TaskEventsManager',
        data_store_mgr: 'DataStoreMgr',
        flow_mgr: 'FlowMgr'
    ) -> None:

        self.config: 'WorkflowConfig' = config
        self.stop_point = config.stop_point or config.final_point
        self.workflow_db_mgr: 'WorkflowDatabaseManager' = workflow_db_mgr
        self.task_events_mgr: 'TaskEventsManager' = task_events_mgr
        # TODO this is ugly:
        self.task_events_mgr.spawn_func = self.spawn_on_output
        self.data_store_mgr: 'DataStoreMgr' = data_store_mgr
        self.flow_mgr: 'FlowMgr' = flow_mgr

        self.do_reload = False
        self.max_future_offset: Optional['IntervalBase'] = None
        self._prev_runahead_base_point: Optional['PointBase'] = None
        self._prev_runahead_sequence_points: Optional[Set['PointBase']] = None
        self.runahead_limit_point: Optional['PointBase'] = None

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
        self.tasks_to_hold: Set[Tuple[str, 'PointBase']] = set()

    def set_stop_task(self, task_id):
        """Set stop after a task."""
        tokens = Tokens(task_id, relative=True)
        name = tokens['task']
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
        elif (
            itask.point in self.main_pool
            and itask.identity in self.main_pool[itask.point]
        ):
            self.main_pool[itask.point][itask.identity] = itask
            self.main_pool_changed = True

    def load_from_point(self):
        """Load the task pool for the workflow start point.

        Add every parentless task out to the runahead limit.
        """
        flow_num = self.flow_mgr.get_new_flow(
            f"original flow from {self.config.start_point}")
        self.compute_runahead()
        for name in self.config.get_task_name_list():
            tdef = self.config.get_taskdef(name)
            point = tdef.first_point(self.config.start_point)
            self.spawn_to_rh_limit(tdef, point, {flow_num})

    def add_to_pool(self, itask, is_new: bool = True) -> None:
        """Add a task to the hidden (if not satisfied) or main task pool.

        If the task already exists in the hidden pool and is satisfied, move it
        to the main pool.

        (is_new is False inidcates load from DB at restart).
        """
        if itask.is_task_prereqs_not_done() and not itask.is_manual_submit:
            # Add to hidden pool if not satisfied.
            self.hidden_pool.setdefault(itask.point, {})
            self.hidden_pool[itask.point][itask.identity] = itask
            self.hidden_pool_changed = True
            LOG.debug(f"[{itask}] added to hidden task pool")
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
            self.main_pool.setdefault(itask.point, {})
            self.main_pool[itask.point][itask.identity] = itask
            self.main_pool_changed = True
            LOG.debug(f"[{itask}] added to main task pool")

            self.create_data_store_elements(itask)

        if is_new:
            # Add row to "task_states" table.
            now = get_current_time_string()
            self.workflow_db_mgr.put_insert_task_states(
                itask,
                {
                    "time_created": now,
                    "time_updated": now,
                    "status": itask.state.status,
                    "flow_nums": serialise(itask.flow_nums)
                }
            )
            # Add row to "task_outputs" table:
            self.workflow_db_mgr.put_insert_task_outputs(itask)

        if itask.tdef.max_future_prereq_offset is not None:
            # (Must do this once added to the pool).
            self.set_max_future_offset()

    def create_data_store_elements(self, itask):
        """Create the node window elements about given task proxy."""
        # Register pool node reference
        self.data_store_mgr.add_pool_node(itask.tdef.name, itask.point)
        # Create new data-store n-distance graph window about this task
        self.data_store_mgr.increment_graph_window(itask)
        self.data_store_mgr.delta_task_state(itask)
        self.data_store_mgr.delta_task_held(itask)
        self.data_store_mgr.delta_task_queued(itask)
        self.data_store_mgr.delta_task_runahead(itask)

    def release_runahead_tasks(self):
        """Release tasks below the runahead limit.

        Return True if any tasks are released, else False.
        Call when RH limit changes.
        """
        if not self.main_pool or not self.runahead_limit_point:
            # (At start-up main pool might not exist yet)
            return False

        released = False

        # An intermediate list is needed here: auto-spawning of parentless
        # tasks can cause the task pool to change size during iteration.
        release_me = [
            itask
            for point, itask_id_map in self.main_pool.items()
            for itask in itask_id_map.values()
            if point <= self.runahead_limit_point
            if itask.state.is_runahead
        ]

        for itask in release_me:
            self.rh_release_and_queue(itask)
            self.spawn_to_rh_limit(
                itask.tdef,
                itask.tdef.next_point(itask.point),
                itask.flow_nums
            )
            released = True

        return released

    def compute_runahead(self, force=False) -> bool:
        """Compute the runahead limit; return True if it changed.

        To be called if:
        * The runahead base point might have changed:
           - a task completed expected outputs, or expired
           - (Cylc7 back compat: a task succeeded or failed)
        * The max future offset might have changed.
        * The runahead limit config or task pool might have changed (reload).

        Start from earliest point with unfinished tasks. Partially satisfied
        and incomplete tasks count too because they still need to run.

        The limit itself is limited by workflow stop point, if there is one,
        and adjusted upward on the fly if tasks with future offsets appear.

        With force=True we recompute the limit even if the base point has not
        changed (needed if max_future_offset changed, or on reload).
        """
        points: List['PointBase'] = []
        if not self.main_pool:
            # Start at first point in each sequence, after the initial point.
            points = list({
                seq.get_first_point(self.config.start_point)
                for seq in self.config.sequences
            })
        else:
            # Find the earliest point with unfinished tasks.
            for point, itasks in sorted(self.get_tasks_by_point().items()):
                if (
                    points  # got the limit already so this point too
                    or any(
                        not itask.state(
                            TASK_STATUS_FAILED,
                            TASK_STATUS_SUCCEEDED,
                            TASK_STATUS_EXPIRED
                        )
                        or (
                            # For Cylc 7 back-compat, ignore incomplete tasks.
                            # (Success is required in back-compat mode, so
                            # failedtasks end up as incomplete; and Cylc 7
                            # ignores failed tasks in computing the limit).
                            itask.state.outputs.is_incomplete()
                            and not cylc.flow.flags.cylc7_back_compat
                        )
                        for itask in itasks
                    )
                ):
                    points.append(point)
        if not points:
            return False
        base_point = min(points)

        if self._prev_runahead_base_point is None:
            self._prev_runahead_base_point = base_point

        if (
            not force
            and self.runahead_limit_point is not None
            and (
                base_point == self._prev_runahead_base_point
                or self.runahead_limit_point == self.stop_point
            )
        ):
            # No need to recompute the list of points if the base point did not
            # change or the runahead limit is already at stop point.
            return False

        try:
            limit = int(self.config.runahead_limit)  # type: ignore
        except TypeError:
            count_cycles = False
            limit = self.config.runahead_limit
        else:
            count_cycles = True

        # Get all cycle points possible after the runahead base point.
        if (
            not force
            and self._prev_runahead_sequence_points
            and base_point == self._prev_runahead_base_point
        ):
            # Cache for speed.
            sequence_points = self._prev_runahead_sequence_points
        else:
            # Recompute possible points.
            sequence_points = set()
            for sequence in self.config.sequences:
                seq_point = sequence.get_next_point(base_point)
                count = 1
                while seq_point is not None:
                    if count_cycles:
                        # P0 allows only the base cycle point to run.
                        if count > 1 + limit:
                            break
                    else:
                        # PT0H allows only the base cycle point to run.
                        if seq_point > base_point + limit:
                            break
                    count += 1
                    sequence_points.add(seq_point)
                    seq_point = sequence.get_next_point(seq_point)
            self._prev_runahead_sequence_points = sequence_points
            self._prev_runahead_base_point = base_point

        points = set(points).union(sequence_points)

        if count_cycles:
            # Some sequences may have different intervals.
            limit_point = sorted(points)[:(limit + 1)][-1]
        else:
            # We already stopped at the runahead limit.
            limit_point = sorted(points)[-1]

        # Adjust for future offset and stop point, if necessary.
        pre_adj_limit = limit_point
        if self.max_future_offset is not None:
            limit_point += self.max_future_offset
            LOG.debug(f"{pre_adj_limit} -> {limit_point} (future offset)")
        if self.stop_point and limit_point > self.stop_point:
            limit_point = self.stop_point
            LOG.debug(f"{pre_adj_limit} -> {limit_point} (stop point)")
        LOG.info(f"Runahead limit: {limit_point}")

        self.runahead_limit_point = limit_point
        return True

    def update_flow_mgr(self):
        flow_nums_seen = set()
        for itask in self.get_all_tasks():
            flow_nums_seen.update(itask.flow_nums)
        self.flow_mgr.load_from_db(flow_nums_seen)

    def load_abs_outputs_for_restart(self, row_idx, row):
        cycle, name, output = row
        self.abs_outputs_done.add((cycle, name, output))

    def load_db_task_pool_for_restart(self, row_idx, row):
        """Load tasks from DB task pool/states/jobs tables.

        Output completion status is loaded from the DB, and tasks recorded
        as submitted or running are polled to confirm their true status.
        Tasks are added to queues again on release from runahead pool.

        """
        if row_idx == 0:
            LOG.info("LOADING task proxies")
        # Create a task proxy corresponding to this DB entry.
        (cycle, name, flow_nums, is_late, status, is_held, submit_num, _,
         platform_name, time_submit, time_run, timeout, outputs_str) = row

        try:
            itask = TaskProxy(
                self.config.get_taskdef(name),
                get_point(cycle),
                deserialise(flow_nums),
                status=status,
                is_held=is_held,
                submit_num=submit_num,
                is_late=bool(is_late)
            )
        except WorkflowConfigError:
            LOG.exception(
                f'ignoring task {name} from the workflow run database\n'
                '(its task definition has probably been deleted).')
        except Exception:
            LOG.exception(f'could not load task {name}')
        else:
            if status in (
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED,
                    TASK_STATUS_SUCCEEDED
            ):
                # update the task proxy with platform
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
                # Re-prepare same submit.
                itask.submit_num -= 1

            # Running or finished task can have completed custom outputs.
            if itask.state(
                    TASK_STATUS_RUNNING,
                    TASK_STATUS_FAILED,
                    TASK_STATUS_SUCCEEDED
            ):
                for message in json.loads(outputs_str):
                    itask.state.outputs.set_completion(message, True)
                    self.data_store_mgr.delta_task_output(itask, message)

            if platform_name and status != TASK_STATUS_WAITING:
                itask.summary['platforms_used'][
                    int(submit_num)] = platform_name
            LOG.info(
                f"+ {cycle}/{name} {status}{' (held)' if is_held else ''}")

            # Update prerequisite satisfaction status from DB
            sat = {}
            for prereq_name, prereq_cycle, prereq_output, satisfied in (
                    self.workflow_db_mgr.pri_dao.select_task_prerequisites(
                        cycle,
                        name,
                        flow_nums,
                    )
            ):
                key = (prereq_cycle, prereq_name, prereq_output)
                sat[key] = satisfied if satisfied != '0' else False

            for itask_prereq in itask.state.prerequisites:
                for key, _ in itask_prereq.satisfied.items():
                    itask_prereq.satisfied[key] = sat[key]

            if itask.state_reset(status, is_runahead=True):
                self.data_store_mgr.delta_task_runahead(itask)
            self.add_to_pool(itask, is_new=False)

            # All tasks load as runahead-limited, but finished and manually
            # triggered tasks (incl. --start-task's) can be released now.
            if (
                itask.state(
                    TASK_STATUS_FAILED,
                    TASK_STATUS_SUCCEEDED,
                    TASK_STATUS_EXPIRED
                )
                or itask.is_manual_submit
            ):
                self.rh_release_and_queue(itask)

            self.compute_runahead()
            self.release_runahead_tasks()

    def load_db_task_action_timers(self, row_idx, row):
        """Load a task action timer, e.g. event handlers, retry states."""
        if row_idx == 0:
            LOG.info("LOADING task action timers")
        (cycle, name, ctx_key_raw, ctx_raw, delays_raw, num, delay,
         timeout) = row
        id_ = Tokens(
            cycle=cycle,
            task=name,
        ).relative_id
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
        LOG.info("+ %s/%s %s" % (cycle, name, ctx_key))
        if ctx_key == "poll_timer":
            itask = self._get_main_task_by_id(id_)
            if itask is None:
                LOG.warning("%(id)s: task not found, skip" % {"id": id_})
                return
            itask.poll_timer = TaskActionTimer(
                ctx, delays, num, delay, timeout)
        elif ctx_key[0] == "try_timers":
            itask = self._get_main_task_by_id(id_)
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

    def load_db_tasks_to_hold(self):
        """Update the tasks_to_hold set with the tasks stored in the
        database."""
        self.tasks_to_hold.update(
            (name, get_point(cycle)) for name, cycle in
            self.workflow_db_mgr.pri_dao.select_tasks_to_hold()
        )

    def rh_release_and_queue(self, itask) -> None:
        """Release a task from runahead limiting, and queue it if ready.

        Check the task against the RH limit before calling this method (in
        forced triggering we need to release even if beyond the limit).
        """
        if itask.state_reset(is_runahead=False):
            self.data_store_mgr.delta_task_runahead(itask)
        if all(itask.is_ready_to_run()):
            # (otherwise waiting on xtriggers etc.)
            self.queue_task(itask)

    def _get_spawned_or_merged_task(
        self, point: 'PointBase', name: str, flow_nums: 'FlowNums'
    ) -> Optional[TaskProxy]:
        """Return new or existing task point/name with merged flow_nums"""
        taskid = Tokens(cycle=str(point), task=name).relative_id
        ntask = (
            self._get_hidden_task_by_id(taskid)
            or self._get_main_task_by_id(taskid)
        )
        if ntask is None:
            # ntask does not exist: spawn it in the flow.
            ntask = self.spawn_task(name, point, flow_nums)
        else:
            # ntask already exists (n=0 or incomplete): merge flows.
            self.merge_flows(ntask, flow_nums)
        return ntask  # may be None

    def spawn_to_rh_limit(self, tdef, point, flow_nums) -> None:
        """Spawn parentless task instances from point to runahead limit."""
        if not flow_nums:
            # force-triggered no-flow task.
            return
        if self.runahead_limit_point is None:
            self.compute_runahead()
        while point is not None and (point <= self.runahead_limit_point):
            if tdef.is_parentless(point):
                ntask = self._get_spawned_or_merged_task(
                    point, tdef.name, flow_nums
                )
                if ntask is not None:
                    self.add_to_pool(ntask)
                    self.rh_release_and_queue(ntask)
            point = tdef.next_point(point)

        # Once more (for the rh-limited task: don't rh release it!)
        if point is not None and tdef.is_parentless(point):
            ntask = self._get_spawned_or_merged_task(
                point, tdef.name, flow_nums
            )
            if ntask is not None:
                self.add_to_pool(ntask)

    def remove(self, itask, reason=""):
        """Remove a task from the pool (e.g. after a reload)."""
        msg = "task proxy removed"
        if reason:
            msg += f" ({reason})"

        try:
            del self.hidden_pool[itask.point][itask.identity]
        except KeyError:
            pass
        else:
            # e.g. for suicide of partially satisfied task
            self.hidden_pool_changed = True
            if not self.hidden_pool[itask.point]:
                del self.hidden_pool[itask.point]
            LOG.debug(f"[{itask}] {msg}")
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
            LOG.debug(f"[{itask}] {msg}")
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

    def _get_hidden_task_by_id(self, id_: str) -> Optional[TaskProxy]:
        """Return runahead pool task by ID if it exists, or None."""
        for itask_ids in list(self.hidden_pool.values()):
            with suppress(KeyError):
                return itask_ids[id_]
        return None

    def _get_main_task_by_id(self, id_: str) -> Optional[TaskProxy]:
        """Return main pool task by ID if it exists, or None."""
        for itask_ids in list(self.main_pool.values()):
            with suppress(KeyError):
                return itask_ids[id_]
        return None

    def queue_task(self, itask: TaskProxy) -> None:
        """Queue a task that is ready to run."""
        if itask.state_reset(is_queued=True):
            self.data_store_mgr.delta_task_queued(itask)
            self.task_queue_mgr.push_task(itask)

    def release_queued_tasks(self):
        """Return list of queue-released tasks awaiting job prep.

        Note:
            Tasks can hang about for a while between being released and
            entering the PREPARING state for various reasons. This method
            returns tasks which are awaiting job prep irrespective of whether
            they have been previously returned.

        """
        # count active tasks by name
        # {task_name: number_of_active_instances, ...}
        active_task_counter = Counter()

        # tasks which have entered the submission pipeline but have not yet
        # entered the PREPARING state
        pre_prep_tasks = []

        for itask in self.get_tasks():
            # populate active_task_counter and pre_prep_tasks together to
            # avoid iterating the task pool twice
            if itask.waiting_on_job_prep:
                # a task which has entered the submission pipeline
                # for the purposes of queue limiting this should be treated
                # the same as an active task
                active_task_counter.update([itask.tdef.name])
                pre_prep_tasks.append(itask)
            elif itask.state(
                TASK_STATUS_PREPARING,
                TASK_STATUS_SUBMITTED,
                TASK_STATUS_RUNNING,
            ):
                # an active task
                active_task_counter.update([itask.tdef.name])

        # release queued tasks
        released = self.task_queue_mgr.release_tasks(active_task_counter)

        for itask in released:
            itask.state_reset(is_queued=False)
            itask.waiting_on_job_prep = True
            self.data_store_mgr.delta_task_queued(itask)

            if cylc.flow.flags.cylc7_back_compat:
                # Cylc 7 Back Compat: spawn downstream to cause Cylc 7 style
                # stalls - with unsatisfied waiting tasks - even with single
                # prerequisites (which result in incomplete tasks in Cylc 8).
                # We do it here (rather than at runhead release) to avoid
                # pre-spawning out to the runahead limit.
                self.spawn_on_all_outputs(itask)

        # Note: released and pre_prep_tasks can overlap
        return list(set(released + pre_prep_tasks))

    def get_min_point(self):
        """Return the minimum cycle point currently in the pool."""
        cycles = list(self.main_pool)
        minc = None
        if cycles:
            minc = min(cycles)
        return minc

    def set_max_future_offset(self):
        """Calculate the latest required future trigger offset."""
        orig = self.max_future_offset
        max_offset = None
        for itask in self.get_tasks():
            if (
                itask.tdef.max_future_prereq_offset is not None
                and (
                    max_offset is None or
                    itask.tdef.max_future_prereq_offset > max_offset
                )
            ):
                max_offset = itask.tdef.max_future_prereq_offset
        self.max_future_offset = max_offset
        if max_offset != orig and self.compute_runahead(force=True):
            self.release_runahead_tasks()

    def set_do_reload(self, config: 'WorkflowConfig') -> None:
        """Set the task pool to reload mode."""
        self.config = config
        self.stop_point = config.stop_point or config.final_point
        self.do_reload = True

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

    def reload_taskdefs(self) -> None:
        """Reload the definitions of task proxies in the pool.

        Orphaned tasks (whose definitions were removed from the workflow):
        - remove if not active yet
        - if active, leave them but prevent them from spawning children on
          subsequent outputs
        Otherwise: replace task definitions but copy over existing outputs etc.

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
                    LOG.warning(
                        f"[{itask}] will not spawn children "
                        "- task definition removed"
                    )
            else:
                new_task = TaskProxy(
                    self.config.get_taskdef(itask.tdef.name),
                    itask.point, itask.flow_nums, itask.state.status)
                itask.copy_to_reload_successor(new_task)
                self._swap_out(new_task)
                LOG.info(f"[{itask}] reloaded task definition")
                if itask.state(*TASK_STATUSES_ACTIVE):
                    LOG.warning(
                        f"[{itask}] active with pre-reload settings"
                    )
                elif itask.state(TASK_STATUS_PREPARING):
                    # Job file might have been written at this point?
                    LOG.warning(
                        f"[{itask}] may be active with pre-reload settings"
                    )

        # Reassign live tasks to the internal queue
        del self.task_queue_mgr
        self.task_queue_mgr = IndepQueueManager(
            self.config.cfg['scheduling']['queues'],
            self.config.get_task_name_list(),
            self.config.runtime['descendants']
        )

        # Now queue all tasks that are ready to run
        for itask in self.get_tasks():
            # Recreate data store elements from main pool.
            self.create_data_store_elements(itask)
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
                self.queue_task(itask)

        self.do_reload = False

    def set_stop_point(self, stop_point: 'PointBase') -> bool:
        """Set the workflow stop cycle point.

        And reset the runahead limit if less than the stop point.
        """
        if self.stop_point == stop_point:
            LOG.info(f"Stop point unchanged: {stop_point}")
            return False

        LOG.info("Setting stop point: {stop_point}")
        self.stop_point = stop_point

        if (
            self.runahead_limit_point is not None
            and self.runahead_limit_point > stop_point
        ):
            self.runahead_limit_point = stop_point
            # Now handle existing waiting tasks (e.g. xtriggered).
            for itask in self.get_all_tasks():
                if (
                    itask.point > stop_point
                    and itask.state(TASK_STATUS_WAITING)
                    and itask.state_reset(is_runahead=True)
                ):
                    self.data_store_mgr.delta_task_runahead(itask)
        return True

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

        return not any(
            (
                stop_mode in [StopMode.REQUEST_CLEAN, StopMode.REQUEST_KILL]
                and itask.state(*TASK_STATUSES_ACTIVE)
                and not itask.state.kill_failed
            )
            # we don't need to check for preparing tasks because they will be
            # reset to waiting on restart
            for itask in self.get_tasks()
        )

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
                "Orphaned tasks (kill failed):\n"
                + "\n".join(
                    f"* {itask.identity} ({itask.state.status})"
                    for itask in orphans_kill_failed
                )
            )
        if orphans:
            LOG.warning(
                "Orphaned tasks:\n"
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

    def log_incomplete_tasks(self):
        """Log finished but incomplete tasks; return True if there any."""
        incomplete = []
        for itask in self.get_tasks():
            if not itask.state(*TASK_STATUSES_FINAL):
                continue
            outputs = itask.state.outputs.get_incomplete()
            if outputs:
                incomplete.append((itask.identity, outputs))

        if incomplete:
            LOG.warning(
                "Incomplete tasks:\n"
                + "\n".join(
                    f"  * {id_} did not complete required outputs: {outputs}"
                    for id_, outputs in incomplete
                )
            )
            return True
        return False

    def log_unsatisfied_prereqs(self):
        """Log unsatisfied prerequisites in the hidden pool.

        Return True if any, ignoring:
            - prerequisites beyond the stop point
            - dependence on tasks beyond the stop point
            (can be caused by future triggers)
        """
        unsat = {}
        for itask in self.get_hidden_tasks():
            task_point = point = itask.point
            if task_point > self.stop_point:
                continue
            for pre in itask.state.get_unsatisfied_prerequisites():
                point, name, output = pre
                if get_point(point) > self.stop_point:
                    continue
                if itask.identity not in unsat:
                    unsat[itask.identity] = []
                unsat[itask.identity].append(f"{point}/{name}:{output}")
        if unsat:
            LOG.warning(
                "Partially satisfied prerequisites:\n"
                + "\n".join(
                    f"  * {id_} is waiting on {others}"
                    for id_, others in unsat.items()
                )
            )
            return True
        else:
            return False

    def is_stalled(self) -> bool:
        """Return whether the workflow is stalled.

        Is stalled if not paused and contains only:
          - incomplete tasks
          - partially satisfied prerequisites (below stop point)
          - runahead-limited tasks (held back by the above)
        """
        if any(
            itask.state(
                *TASK_STATUSES_ACTIVE,
                TASK_STATUS_PREPARING
            ) or (
                itask.state(TASK_STATUS_WAITING)
                and not itask.state.is_runahead
            ) for itask in self.get_tasks()
        ):
            return False

        incomplete = self.log_incomplete_tasks()
        unsatisfied = self.log_unsatisfied_prereqs()
        if incomplete or unsatisfied:
            LOG.critical("Workflow stalled")
            return True
        else:
            return False

    def hold_active_task(self, itask: TaskProxy) -> None:
        if itask.state_reset(is_held=True):
            self.data_store_mgr.delta_task_held(itask)
        self.tasks_to_hold.add((itask.tdef.name, itask.point))
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)

    def release_held_active_task(self, itask: TaskProxy) -> None:
        if itask.state_reset(is_held=False):
            self.data_store_mgr.delta_task_held(itask)
            if (not itask.state.is_runahead) and all(itask.is_ready_to_run()):
                self.queue_task(itask)
        self.tasks_to_hold.discard((itask.tdef.name, itask.point))
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)

    def set_hold_point(self, point: 'PointBase') -> None:
        """Set the point after which all tasks must be held."""
        self.hold_point = point
        for itask in self.get_all_tasks():
            if itask.point > point:
                self.hold_active_task(itask)
        self.workflow_db_mgr.put_workflow_hold_cycle_point(point)

    def hold_tasks(self, items: Iterable[str]) -> int:
        """Hold tasks with IDs matching the specified items."""
        # Hold active tasks:
        itasks, future_tasks, unmatched = self.filter_task_proxies(
            items,
            warn=False,
            future=True,
        )
        for itask in itasks:
            self.hold_active_task(itask)
        # Set future tasks to be held:
        for name, cycle in future_tasks:
            self.data_store_mgr.delta_task_held((name, cycle, True))
        self.tasks_to_hold.update(future_tasks)
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)
        LOG.debug(f"Tasks to hold: {self.tasks_to_hold}")
        return len(unmatched)

    def release_held_tasks(self, items: Iterable[str]) -> int:
        """Release held tasks with IDs matching any specified items."""
        # Release active tasks:
        itasks, future_tasks, unmatched = self.filter_task_proxies(
            items,
            warn=False,
            future=True,
        )
        for itask in itasks:
            self.release_held_active_task(itask)
        # Unhold future tasks:
        for name, cycle in future_tasks:
            self.data_store_mgr.delta_task_held((name, cycle, False))
        self.tasks_to_hold.difference_update(future_tasks)
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)
        LOG.debug(f"Tasks to hold: {self.tasks_to_hold}")
        return len(unmatched)

    def release_hold_point(self) -> None:
        """Unset the workflow hold point and release all held active tasks."""
        self.hold_point = None
        for itask in self.get_all_tasks():
            self.release_held_active_task(itask)
        self.tasks_to_hold.clear()
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)
        self.workflow_db_mgr.delete_workflow_hold_cycle_point()

    def check_abort_on_task_fails(self):
        """Check whether workflow should abort on task failure.

        Return True if a task failed and `--abort-if-any-task-fails` was given.
        """
        return self.abort_task_failed

    def spawn_on_output(self, itask, output, forced=False):
        """Spawn and update itask's children, remove itask if finished.

        Also set a the abort-on-task-failed flag if necessary.

        If not flowing on:
            - update existing children but don't spawn new ones
            - unless forced (manual command): spawn but with no flow number

        If an absolute output is completed update the store of completed abs
        outputs, and update the prerequisites of every instance of the child
        in the pool. (And in self.spawn() use the store of completed abs
        outputs to satisfy any tasks with abs prerequisites).

        Args:
            tasks: List of identifiers or task globs.
            outputs: List of outputs to spawn on.
            forced: If True this is a manual spawn command.

        """
        self.workflow_db_mgr.put_update_task_outputs(itask)
        if (
            output == TASK_OUTPUT_FAILED
            and self.expected_failed_tasks is not None
            and itask.identity not in self.expected_failed_tasks
        ):
            self.abort_task_failed = True
        try:
            children = itask.graph_children[output]
        except KeyError:
            # No children depend on this output
            children = []

        suicide = []
        for c_name, c_point, is_abs in children:
            if is_abs:
                self.abs_outputs_done.add(
                    (str(itask.point), itask.tdef.name, output))
                self.workflow_db_mgr.put_insert_abs_output(
                    str(itask.point), itask.tdef.name, output)
                self.workflow_db_mgr.process_queued_ops()

            c_taskid = Tokens(
                cycle=str(c_point),
                task=c_name,
            ).relative_id
            c_task = (
                self._get_hidden_task_by_id(c_taskid)
                or self._get_main_task_by_id(c_taskid)
            )
            if c_task is not None and c_task != itask:
                # (Avoid self-suicide: A => !A)
                self.merge_flows(c_task, itask.flow_nums)
                self.workflow_db_mgr.put_insert_task_states(
                    c_task,
                    {
                        "status": c_task.state.status,
                        "flow_nums": serialise(c_task.flow_nums)
                    }
                )
                # self.workflow_db_mgr.process_queued_ops()
            elif (
                c_task is None
                and (itask.flow_nums or forced)
                and not itask.flow_wait
            ):
                # If child is not in the pool already, and parent belongs to a
                # flow (so it can spawn children), and parent is not waiting
                # for an upcoming flow merge before spawning ... then spawn it.
                c_task = self.spawn_task(c_name, c_point, itask.flow_nums)

            if c_task is not None:
                # Have child task, update its prerequisites.
                if is_abs:
                    tasks, *_ = self.filter_task_proxies(
                        [f'*/{c_name}'],
                        warn=False,
                    )
                    if c_task not in tasks:
                        tasks.append(c_task)
                else:
                    tasks = [c_task]
                for t in tasks:
                    t.state.satisfy_me({
                        (str(itask.point), itask.tdef.name, output)
                    })
                    self.data_store_mgr.delta_task_prerequisite(t)
                    # Add it to the hidden pool or move it to the main pool.
                    self.add_to_pool(t)

                    if t.point <= self.runahead_limit_point:
                        self.rh_release_and_queue(t)

                    # Event-driven suicide.
                    if (
                        t.state.suicide_prerequisites and
                        t.state.suicide_prerequisites_all_satisfied()
                    ):
                        suicide.append(t)

        for c_task in suicide:
            msg = self.__class__.SUICIDE_MSG
            if c_task.state(
                    TASK_STATUS_PREPARING,
                    TASK_STATUS_SUBMITTED,
                    TASK_STATUS_RUNNING,
                    is_held=False):
                msg += " suiciding while active"
            self.remove(c_task, msg)

        if not forced and output in [
            TASK_OUTPUT_SUCCEEDED,
            TASK_OUTPUT_EXPIRED,
            TASK_OUTPUT_FAILED
        ]:
            self.remove_if_complete(itask)

    def remove_if_complete(self, itask):
        """Remove finished itask if required outputs are complete.

        Cylc 8:
            - if complete:
              - remove task and recompute runahead
            - else (incomplete):
              - retain

        Cylc 7 back compat:
            - if succeeded:
                - remove task and recompute runahead
            else (failed):
                - retain and recompute runahead
                  (C7 failed tasks don't count toward runahead limit)
        """
        if cylc.flow.flags.cylc7_back_compat:
            if not itask.state(TASK_STATUS_FAILED):
                self.remove(itask, 'finished')
            if self.compute_runahead():
                self.release_runahead_tasks()
        else:
            incomplete = itask.state.outputs.get_incomplete()
            if incomplete:
                # Retain as incomplete.
                LOG.warning(
                    f"[{itask}] did not complete required outputs:"
                    f" {incomplete}"
                )
            else:
                # Remove as completed.
                self.remove(itask, 'finished')
                if itask.identity == self.stop_task_id:
                    self.stop_task_finished = True
                if self.compute_runahead():
                    self.release_runahead_tasks()

    def spawn_on_all_outputs(
        self, itask: TaskProxy, completed_only: bool = False
    ) -> None:
        """Spawn on all (or all completed) task outputs.

        If completed_only is False:
           Used in Cylc 7 Back Compat mode for pre-spawning waiting tasks. Do
           not set the associated prerequisites of spawned children satisfied.

        If completed_only is True:
           Used to retroactively spawn on already-completed outputs when a flow
           merges into a force-triggered no-flow task. In this case, do set the
           associated prerequisites of spawned children to satisifed.

        """
        if completed_only:
            outputs = itask.state.outputs.get_completed()
        else:
            outputs = itask.state.outputs._by_message

        for output in outputs:
            try:
                children = itask.graph_children[output]
            except KeyError:
                continue

            for c_name, c_point, _ in children:
                c_taskid = Tokens(
                    cycle=str(c_point),
                    task=c_name,
                ).relative_id
                c_task = (
                    self._get_hidden_task_by_id(c_taskid)
                    or self._get_main_task_by_id(c_taskid)
                )
                if c_task is not None:
                    # already spawned
                    continue

                c_task = self.spawn_task(c_name, c_point, itask.flow_nums)
                if c_task is None:
                    # not spawnable
                    continue
                if completed_only:
                    c_task.state.satisfy_me({
                        (str(itask.point), itask.tdef.name, output)
                    })
                    self.data_store_mgr.delta_task_prerequisite(c_task)
                self.add_to_pool(c_task)
                if (
                    self.runahead_limit_point is not None
                    and c_task.point <= self.runahead_limit_point
                ):
                    self.rh_release_and_queue(c_task)

    def can_spawn(self, name: str, point: 'PointBase') -> bool:
        """Return True if the task with the given name & point is within
        various workflow limits."""
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
                'Not spawning %s/%s: before initial cycle point', point, name)
            return False
        elif self.config.final_point and point > self.config.final_point:
            # Only happens on manual trigger beyond FCP
            LOG.debug(
                'Not spawning %s/%s: beyond final cycle point', point, name)
            return False
        return True

    def spawn_task(
        self,
        name: str,
        point: 'PointBase',
        flow_nums: Set[int],
        force: bool = False,
        is_manual_submit: bool = False,
        flow_wait: bool = False,
    ) -> Optional[TaskProxy]:
        """Spawn point/name. Return the spawned task, or None.

        Force arg used in manual triggering.
        """
        if not self.can_spawn(name, point):
            return None

        # Get submit number by flow_nums {flow_nums: submit_num, ...}
        snums = self.workflow_db_mgr.pri_dao.select_submit_nums(
            name, str(point)
        )
        try:
            submit_num = max(s for s in snums.keys())
        except ValueError:
            # Task never spawned in any flow.
            submit_num = 0

        flow_wait_done = False
        for f_wait, old_fnums in snums.values():
            # Flow_nums of previous instances.
            if (
                not force and
                set.intersection(flow_nums, old_fnums)
            ):
                if f_wait:
                    flow_wait_done = f_wait
                    break
                # To avoid "conditional reflow" with (e.g.) "foo | bar => baz".
                LOG.warning(
                    f"Task {point}/{name} already spawned in {flow_nums}"
                )
                return None

        # Spawn if on-sequence and within recurrence bounds.
        taskdef = self.config.get_taskdef(name)
        if not taskdef.is_valid_point(point):
            LOG.warning(
                self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE.format(
                    taskdef.name, point
                )
            )
            return None

        itask = TaskProxy(
            taskdef,
            point,
            flow_nums,
            submit_num=submit_num,
            is_manual_submit=is_manual_submit,
            flow_wait=flow_wait
        )
        if (name, point) in self.tasks_to_hold:
            LOG.info(f"[{itask}] holding (as requested earlier)")
            self.hold_active_task(itask)
        elif self.hold_point and itask.point > self.hold_point:
            # Hold if beyond the workflow hold point
            LOG.info(
                f"[{itask}] holding (beyond workflow "
                f"hold point: {self.hold_point})"
            )
            self.hold_active_task(itask)

        if self.stop_point and itask.point <= self.stop_point:
            future_trigger_overrun = False
            for pct in itask.state.prerequisites_get_target_points():
                if pct > self.stop_point:
                    future_trigger_overrun = True
                    break
            if future_trigger_overrun:
                LOG.warning(
                    f"[{itask}] won't run: depends on a task beyond "
                    f"the stop point ({self.stop_point})"
                )

        # Satisfy any absolute triggers.
        if (
            itask.tdef.has_abs_triggers and
            itask.state.prerequisites_are_not_all_satisfied()
        ):
            itask.state.satisfy_me(self.abs_outputs_done)

        if flow_wait_done:
            for outputs_str, fnums in (
                self.workflow_db_mgr.pri_dao.select_task_outputs(
                    itask.tdef.name, str(itask.point))
            ).items():
                if flow_nums.intersection(fnums):
                    for msg in json.loads(outputs_str):
                        itask.state.outputs.set_completed_by_msg(msg)
                    break
            LOG.info(f"{itask} spawning on outputs after flow wait")
            self.spawn_on_all_outputs(itask, completed_only=True)
            return None

        LOG.info(f"[{itask}] spawned")
        return itask

    def force_spawn_children(
        self,
        items: Iterable[str],
        outputs: Optional[List[str]] = None,
        flow_num: Optional[int] = None
    ):
        """Spawn downstream children of given outputs, on user command.

        User-facing command name: set_outputs. Creates a transient parent just
        for the purpose of spawning children.

        Args:
            items: Identifiers for matching task definitions, each with the
                form "point/name".
            outputs: List of outputs to spawn on
            flow_num: Flow number to attribute the outputs

        """
        outputs = outputs or [TASK_OUTPUT_SUCCEEDED]
        if flow_num is None:
            flow_nums = None
        else:
            flow_nums = {flow_num}

        n_warnings, task_items = self.match_taskdefs(items)
        for (_, point), taskdef in sorted(task_items.items()):
            # This the parent task:
            itask = TaskProxy(taskdef, point, flow_nums=flow_nums)
            # Spawn children of selected outputs.
            for trig, out, _ in itask.state.outputs.get_all():
                if trig in outputs:
                    LOG.info(f"[{itask}] Forced spawning on {out}")
                    self.spawn_on_output(itask, out, forced=True)

    def _get_active_flow_nums(self):
        fnums = set()
        for itask in self.get_all_tasks():
            fnums.update(itask.flow_nums)
        return fnums

    def remove_tasks(self, items):
        """Remove tasks from the pool."""
        itasks, _, bad_items = self.filter_task_proxies(items)
        for itask in itasks:
            self.remove(itask, 'request')
        return len(bad_items)

    def force_trigger_tasks(
        self, items: Iterable[str],
        flow: List[str],
        flow_wait: bool = False,
        flow_descr: Optional[str] = None
    ) -> int:
        """Manual task triggering.

        Don't get a new flow number for existing n=0 tasks (e.g. incomplete
        tasks). These can carry on in the original flow if retriggered.

        Queue the task if not queued, otherwise release it to run.

        """
        if set(flow).intersection({FLOW_ALL, FLOW_NEW, FLOW_NONE}):
            if len(flow) != 1:
                LOG.warning(
                    f'The "flow" values {FLOW_ALL}, {FLOW_NEW} & {FLOW_NONE}'
                    ' cannot be used in combination with integer flow numbers.'
                )
                return 0
            if flow[0] == FLOW_ALL:
                flow_nums = self._get_active_flow_nums()
            elif flow[0] == FLOW_NEW:
                flow_nums = {self.flow_mgr.get_new_flow(flow_descr)}
            elif flow[0] == FLOW_NONE:
                flow_nums = set()
        else:
            try:
                flow_nums = {int(n) for n in flow}
            except ValueError:
                LOG.warning(
                    f"Trigger ignored, illegal flow values {flow}"
                )
                return 0

        # n_warnings, task_items = self.match_taskdefs(items)
        itasks, future_tasks, unmatched = self.filter_task_proxies(
            items,
            future=True,
            warn=False,
        )

        # Spawn future tasks.
        for name, point in future_tasks:
            # (Flow values already validated by the trigger client).
            itask = self.spawn_task(
                name,
                point,
                flow_nums,
                force=True,
                is_manual_submit=True,
                flow_wait=flow_wait
            )
            if itask is None:
                continue
            self.add_to_pool(itask, is_new=True)
            itasks.append(itask)

        # Trigger matched tasks if not already active.
        for itask in itasks:
            if itask.state(TASK_STATUS_PREPARING, *TASK_STATUSES_ACTIVE):
                LOG.warning(f"[{itask}] ignoring trigger - already active")
                continue
            itask.is_manual_submit = True
            itask.reset_try_timers()
            # (If None, spawner reports cycle bounds errors).
            if itask.state_reset(TASK_STATUS_WAITING):
                # (could also be unhandled failed)
                self.data_store_mgr.delta_task_state(itask)
            # (No need to set prerequisites satisfied here).
            self.add_to_pool(itask)  # move from hidden if necessary.
            if itask.state.is_runahead:
                # Release from runahead, and queue it.
                self.rh_release_and_queue(itask)
                self.spawn_to_rh_limit(
                    itask.tdef,
                    itask.tdef.next_point(itask.point),
                    itask.flow_nums
                )
            else:
                # De-queue it to run now.
                self.task_queue_mgr.force_release_task(itask)

            self.workflow_db_mgr.put_update_task_state(itask)
        return len(unmatched)

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
                job_d = itask.tokens.duplicate(job=str(itask.submit_num))
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
            LOG.warning(f"[{itask}] {msg}")
            self.task_events_mgr.setup_event_handlers(itask, "expired", msg)
            # TODO succeeded and expired states are useless due to immediate
            # removal under all circumstances (unhandled failed is still used).
            if itask.state_reset(TASK_STATUS_EXPIRED, is_held=False):
                self.data_store_mgr.delta_task_state(itask)
                self.data_store_mgr.delta_task_held(itask)
            self.remove(itask, 'expired')
            return True
        return False

    def task_succeeded(self, id_):
        """Return True if task with id_ is in the succeeded state."""
        return any(
            (
                itask.identity == id_
                and itask.state(TASK_STATUS_SUCCEEDED)
            )
            for itask in self.get_tasks()
        )

    def stop_flow(self, flow_num):
        """Stop a given flow from spawning any further.

        Remove the flow number from every task in the pool, and remove any task
        with no remaining flow numbers if it is not already active.
        """
        for itask in self.get_all_tasks():
            try:
                itask.flow_nums.remove(flow_num)
            except KeyError:
                continue
            else:
                if (
                    not itask.state(
                        *TASK_STATUSES_ACTIVE, TASK_STATUS_PREPARING)
                    and not itask.flow_nums
                ):
                    self.remove(itask, "flow stopped")

    def log_task_pool(self, log_lvl=logging.DEBUG):
        """Log content of task and prerequisite pools in debug mode."""
        for pool, name in [
            (self.main_pool_list, "Main"),
            (self.hidden_pool_list, "Hidden")
        ]:
            if pool:
                LOG.log(
                    log_lvl,
                    f"{name} pool:\n"
                    + "\n".join(
                        f"* {itask} status={itask.state.status}"
                        f" runahead={itask.state.is_runahead}"
                        f" queued={itask.state.is_queued}"
                        for itask in pool
                    )
                )

    def filter_task_proxies(
        self,
        ids: Iterable[str],
        warn: bool = True,
        future: bool = False,
    ) -> 'Tuple[List[TaskProxy], Set[Tuple[str, PointBase]], List[str]]':
        """Return task proxies that match names, points, states in items.

        Args:
            ids:
                ID strings.
            warn:
                Whether to log a warning if no matching tasks are found.
            future:
                If True, unmatched IDs will be checked against taskdefs
                and cycle, task pairs will be provided in the future_matched
                argument providing the ID

                * Specifies a cycle point.
                * Is not a pattern. (e.g. `*/foo`).
                * Does not contain a state selector (e.g. `:failed`).

        Returns:
            (matched, future_matched, unmatched)

        """
        matched, unmatched = filter_ids(
            [self.main_pool, self.hidden_pool],
            ids,
            warn=warn,
        )
        future_matched: 'Set[Tuple[str, PointBase]]' = set()
        if future and unmatched:
            future_matched, unmatched = self.match_future_tasks(
                unmatched
            )

        return matched, future_matched, unmatched

    def match_future_tasks(
        self,
        ids: Iterable[str],
    ) -> Tuple[Set[Tuple[str, 'PointBase']], List[str]]:
        """Match task IDs against task definitions (rather than the task pool).

        IDs will be matched providing the ID:

        * Specifies a cycle point.
        * Is not a pattern. (e.g. `*/foo`).
        * Does not contain a state selector (e.g. `:failed`).

        Returns:
            (matched_tasks, unmatched_tasks)

        """
        matched_tasks: 'Set[Tuple[str, PointBase]]' = set()
        unmatched_tasks: 'List[str]' = []
        for id_ in ids:
            try:
                tokens = Tokens(id_, relative=True)
            except ValueError:
                LOG.warning(f'Invalid task ID: {id_}')
                continue
            if (
                not tokens['cycle']
                or not tokens['task']
                or tokens['cycle_sel']
                or tokens['task_sel']
                or contains_fnmatch(id_)
            ):
                # Glob or task state was not matched by active tasks
                if not tokens['task']:
                    # make task globs explicit to make warnings clearer
                    tokens['task'] = '*'
                LOG.warning(
                    'No active tasks matching:'
                    # preserve :selectors when logging the id
                    f' {detokenise(tokens, selectors=True, relative=True)}'
                )
                unmatched_tasks.append(id_)
                continue

            point_str = tokens['cycle']
            name_str = tokens['task']
            if name_str not in self.config.taskdefs:
                if self.config.find_taskdefs(name_str):
                    # It's a family name; was not matched by active tasks
                    LOG.warning(
                        f"No active tasks in the family {name_str}"
                        f' matching: {id_}'
                    )
                else:
                    LOG.warning(self.ERR_TMPL_NO_TASKID_MATCH.format(name_str))
                unmatched_tasks.append(id_)
                continue
            try:
                point_str = standardise_point_string(point_str)
            except PointParsingError as exc:
                LOG.warning(
                    f"{id_} - invalid cycle point: {point_str} ({exc})")
                unmatched_tasks.append(id_)
                continue
            point = get_point(point_str)
            taskdef = self.config.taskdefs[name_str]
            if taskdef.is_valid_point(point):
                matched_tasks.add((taskdef.name, point))
            else:
                LOG.warning(
                    self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE.format(
                        taskdef.name, point
                    )
                )
                unmatched_tasks.append(id_)
                continue
        return matched_tasks, unmatched_tasks

    def match_taskdefs(
        self, ids: Iterable[str]
    ) -> Tuple[int, Dict[Tuple[str, 'PointBase'], 'TaskDef']]:
        """Return matching taskdefs valid for selected cycle points.

        Args:
            items:
                Identifiers for matching task definitions, each with the
                form "point/name".
                Cycle point globs will give a warning and be skipped,
                but task name globs will be matched.
                Task states are ignored.

        """
        n_warnings = 0
        task_items: Dict[Tuple[str, 'PointBase'], 'TaskDef'] = {}
        for id_ in ids:
            try:
                tokens = Tokens(id_, relative=True)
            except ValueError:
                LOG.warning(f'Invalid task ID: {id_}')
                continue
            point_str = tokens['cycle']
            if not tokens['task']:
                # make task globs explicit to make warnings clearer
                tokens['task'] = '*'
            name_str = tokens['task']
            try:
                point_str = standardise_point_string(point_str)
            except PointParsingError as exc:
                LOG.warning(
                    self.ERR_TMPL_NO_TASKID_MATCH.format(
                        f"{tokens.relative_id} ({exc})"
                    )
                )
                n_warnings += 1
                continue
            taskdefs = self.config.find_taskdefs(name_str)
            if not taskdefs:
                LOG.warning(
                    self.ERR_TMPL_NO_TASKID_MATCH.format(
                        tokens.relative_id
                    )
                )
                n_warnings += 1
                continue
            point = get_point(point_str)
            for taskdef in taskdefs:
                if taskdef.is_valid_point(point):
                    task_items[(taskdef.name, point)] = taskdef
                else:
                    if not contains_fnmatch(name_str):
                        LOG.warning(
                            self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE.format(
                                taskdef.name, point
                            )
                        )
                        n_warnings += 1
                    continue
        return n_warnings, task_items

    def merge_flows(self, itask: TaskProxy, flow_nums: 'FlowNums') -> None:
        """Merge flow_nums into itask.flow_nums, for existing itask.

        This is required when we try to spawn a task instance that already
        exists in the pool (i.e., with the same name and cycle point).

        This also performs required spawning / state changing for edge cases.
        """
        if flow_nums == itask.flow_nums:
            # Don't do anything if trying to spawn the same task in the same
            # flow. This arises downstream of an AND trigger (if "A & B => C"
            # and A spawns C first, B will find C is already in the pool),
            # and via suicide triggers ("A =>!A": A tries to spawn itself).
            return

        if (
            itask.state(*TASK_STATUSES_FINAL)
            and itask.state.outputs.get_incomplete()
        ):
            # Re-queue incomplete task to run again in the merged flow.
            LOG.info(f"[{itask}] incomplete task absorbed by new flow.")
            itask.merge_flows(flow_nums)
            itask.state_reset(TASK_STATUS_WAITING)
            self.queue_task(itask)
            self.data_store_mgr.delta_task_state(itask)

        elif not itask.flow_nums or itask.flow_wait:
            # 2. Retro-spawn on completed outputs and continue as merged flow.
            LOG.info(f"[{itask}] spawning on pre-merge outputs")
            itask.merge_flows(flow_nums)
            itask.flow_wait = False
            self.spawn_on_all_outputs(itask, completed_only=True)
            self.spawn_to_rh_limit(
                itask.tdef, itask.next_point(), itask.flow_nums)
        else:
            itask.merge_flows(flow_nums)
