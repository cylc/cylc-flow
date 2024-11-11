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
from contextlib import suppress
import json
import logging
from textwrap import indent
from typing import (
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from cylc.flow import LOG
from cylc.flow.cycling.loader import (
    get_point,
    standardise_point_string,
)
from cylc.flow.exceptions import (
    PlatformLookupError,
    PointParsingError,
    WorkflowConfigError,
)
import cylc.flow.flags
from cylc.flow.flow_mgr import (
    FLOW_ALL,
    FLOW_NEW,
    FLOW_NONE,
    repr_flow_nums,
)
from cylc.flow.id import (
    Tokens,
    detokenise,
    quick_relative_id,
)
from cylc.flow.id_cli import contains_fnmatch
from cylc.flow.id_match import filter_ids
from cylc.flow.platforms import get_platform
from cylc.flow.task_action_timer import (
    TaskActionTimer,
    TimerFlags,
)
from cylc.flow.task_events_mgr import (
    CustomTaskEventHandlerContext,
    EventKey,
    TaskEventMailContext,
    TaskJobLogsRetrieveContext,
)
from cylc.flow.task_id import TaskID
from cylc.flow.task_outputs import (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_SUCCEEDED,
)
from cylc.flow.task_proxy import TaskProxy
from cylc.flow.task_queues.independent import IndepQueueManager
from cylc.flow.task_state import (
    TASK_STATUS_EXPIRED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PREPARING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING,
    TASK_STATUSES_ACTIVE,
    TASK_STATUSES_FINAL,
)
from cylc.flow.task_trigger import TaskTrigger
from cylc.flow.util import deserialise_set
from cylc.flow.workflow_status import StopMode


if TYPE_CHECKING:
    from cylc.flow.config import WorkflowConfig
    from cylc.flow.cycling import (
        IntervalBase,
        PointBase,
    )
    from cylc.flow.data_store_mgr import DataStoreMgr
    from cylc.flow.flow_mgr import (
        FlowMgr,
        FlowNums,
    )
    from cylc.flow.prerequisite import SatisfiedState
    from cylc.flow.task_events_mgr import TaskEventsManager
    from cylc.flow.taskdef import TaskDef
    from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
    from cylc.flow.xtrigger_mgr import XtriggerManager


Pool = Dict['PointBase', Dict[str, TaskProxy]]


class TaskPool:
    """Task pool of a workflow."""

    ERR_TMPL_NO_TASKID_MATCH = "No matching tasks found: {0}"
    ERR_PREFIX_TASK_NOT_ON_SEQUENCE = "Invalid cycle point for task: {0}, {1}"
    SUICIDE_MSG = "suicide trigger"

    def __init__(
        self,
        tokens: 'Tokens',
        config: 'WorkflowConfig',
        workflow_db_mgr: 'WorkflowDatabaseManager',
        task_events_mgr: 'TaskEventsManager',
        xtrigger_mgr: 'XtriggerManager',
        data_store_mgr: 'DataStoreMgr',
        flow_mgr: 'FlowMgr'
    ) -> None:
        self.tokens = tokens
        self.config: 'WorkflowConfig' = config
        self.stop_point = config.stop_point or config.final_point
        self.workflow_db_mgr: 'WorkflowDatabaseManager' = workflow_db_mgr
        self.task_events_mgr: 'TaskEventsManager' = task_events_mgr
        self.task_events_mgr.spawn_func = self.spawn_on_output
        self.xtrigger_mgr: 'XtriggerManager' = xtrigger_mgr
        self.xtrigger_mgr.add_xtriggers(self.config.xtrigger_collator)
        self.data_store_mgr: 'DataStoreMgr' = data_store_mgr
        self.flow_mgr: 'FlowMgr' = flow_mgr

        self.max_future_offset: Optional['IntervalBase'] = None
        self._prev_runahead_base_point: Optional['PointBase'] = None
        self._prev_runahead_sequence_points: Optional[Set['PointBase']] = None
        self.runahead_limit_point: Optional['PointBase'] = None

        # Tasks in the active window of the workflow.
        self.active_tasks: Pool = {}
        self._active_tasks_list: List[TaskProxy] = []
        self.active_tasks_changed = False
        self.tasks_removed = False

        self.hold_point: Optional['PointBase'] = None
        self.abs_outputs_done: Set[Tuple[str, str, str]] = set()

        self.stop_task_id: Optional[str] = None
        self.stop_task_finished = False
        self.abort_task_failed = False
        self.expected_failed_tasks = self.config.get_expected_failed_tasks()

        self.task_name_list = self.config.get_task_name_list()
        self.task_queue_mgr = IndepQueueManager(
            self.config.cfg['scheduling']['queues'],
            self.task_name_list,
            self.config.runtime['descendants']
        )
        self.tasks_to_hold: Set[Tuple[str, 'PointBase']] = set()

    def set_stop_task(self, task_id):
        """Set stop after a task."""
        tokens = Tokens(task_id, relative=True)
        name = tokens['task']
        if name in self.config.taskdefs:
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
            self.workflow_db_mgr.put_workflow_stop_task(None)
            return True
        return False

    def _swap_out(self, itask):
        """Swap old task for new, during reload."""
        if itask.identity in self.active_tasks.get(itask.point, set()):
            self.active_tasks[itask.point][itask.identity] = itask
            self.active_tasks_changed = True

    def load_from_point(self):
        """Load the task pool for the workflow start point.

        Add every parentless task out to the runahead limit.
        """
        flow_num = self.flow_mgr.get_flow_num(
            meta=f"original flow from {self.config.start_point}")
        self.compute_runahead()
        for name in self.task_name_list:
            tdef = self.config.get_taskdef(name)
            point = tdef.first_point(self.config.start_point)
            self.spawn_to_rh_limit(tdef, point, {flow_num})

    def db_add_new_flow_rows(self, itask: TaskProxy) -> None:
        """Add new rows to DB task tables that record flow_nums.

        Call when a new task is spawned or a flow merge occurs.
        """
        # Add row to task_states table.
        self.workflow_db_mgr.put_insert_task_states(itask)
        # Add row to task_outputs table:
        self.workflow_db_mgr.put_insert_task_outputs(itask)

    def add_to_pool(self, itask) -> None:
        """Add a task to the pool."""

        self.active_tasks.setdefault(itask.point, {})
        self.active_tasks[itask.point][itask.identity] = itask
        self.active_tasks_changed = True
        LOG.debug(f"[{itask}] added to active task pool")

        self.create_data_store_elements(itask)

        if itask.tdef.max_future_prereq_offset is not None:
            # (Must do this once added to the pool).
            self.set_max_future_offset()

    def create_data_store_elements(self, itask):
        """Create the node window elements about given task proxy."""
        # Register pool node reference
        self.data_store_mgr.add_pool_node(itask.tdef.name, itask.point)
        # Create new data-store n-distance graph window about this task
        self.data_store_mgr.increment_graph_window(
            itask.tokens,
            itask.point,
            itask.flow_nums,
            is_manual_submit=itask.is_manual_submit,
            itask=itask
        )
        self.data_store_mgr.delta_task_state(itask)

    def release_runahead_tasks(self):
        """Release tasks below the runahead limit.

        Return True if any tasks are released, else False.
        Call when RH limit changes.
        """
        if not self.active_tasks or not self.runahead_limit_point:
            # (At start-up task pool might not exist yet)
            return False

        released = False

        # An intermediate list is needed here: auto-spawning of parentless
        # tasks can cause the task pool to change size during iteration.
        release_me = [
            itask
            for point, itask_id_map in self.active_tasks.items()
            for itask in itask_id_map.values()
            if point <= self.runahead_limit_point
            if itask.state.is_runahead
        ]

        for itask in release_me:
            self.rh_release_and_queue(itask)
            if itask.flow_nums and not itask.is_xtrigger_sequential:
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

        This is a collective task pool computation. Call it once at the end
        of a group operation such as removal of multiple tasks (not after
        every individual task operation).

        Start from earliest point with unfinished tasks. Partially satisfied
        and incomplete tasks count too because they still need to run.

        The limit itself is limited by workflow stop point, if there is one,
        and adjusted upward on the fly if tasks with future offsets appear.

        With force=True we recompute the limit even if the base point has not
        changed (needed if max_future_offset changed, or on reload).

        """
        limit = self.config.runahead_limit  # e.g. P2 or P2D
        count_cycles = False
        with suppress(TypeError):
            # Count cycles (integer cycling, and optional for datetime too).
            ilimit = int(limit)  # type: ignore
            count_cycles = True

        base_point: Optional['PointBase'] = None

        # First get the runahead base point.
        if not self.active_tasks:
            # Find the earliest sequence point beyond the workflow start point.
            base_point = min(
                (
                    point
                    for point in {
                        seq.get_first_point(self.config.start_point)
                        for seq in self.config.sequences
                    }
                    if point is not None
                ),
                default=None,
            )
        else:
            # Find the earliest point with incomplete tasks.
            for point, itasks in sorted(self.get_tasks_by_point().items()):
                # All n=0 tasks are incomplete by definition, but Cylc 7
                # ignores failed ones (it does not ignore submit-failed!).
                if (
                    cylc.flow.flags.cylc7_back_compat and
                    all(
                        itask.state(TASK_STATUS_FAILED)
                        for itask in itasks
                    )
                ):
                    continue
                base_point = point
                break

        if base_point is None:
            return False

        LOG.debug(f"Runahead: base point {base_point}")

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

        # Now generate all possible cycle points from the base point and stop
        # at the runahead limit point. Note both cycle count and time interval
        # limits involve all possible cycles, not just active cycles.
        sequence_points: Set['PointBase'] = set()
        if (
            not force
            and self._prev_runahead_sequence_points
            and base_point == self._prev_runahead_base_point
        ):
            # Cache for speed.
            sequence_points = self._prev_runahead_sequence_points
        else:
            # Recompute possible points.
            for sequence in self.config.sequences:
                seq_point = sequence.get_first_point(base_point)
                count = 1
                while seq_point is not None:
                    if count_cycles:
                        # P0 allows only the base cycle point to run.
                        if count > 1 + ilimit:
                            # this point may be beyond the runahead limit
                            break
                    else:
                        # PT0H allows only the base cycle point to run.
                        if seq_point > base_point + limit:
                            # this point can not be beyond the runahead limit
                            break
                    count += 1
                    sequence_points.add(seq_point)
                    seq_point = sequence.get_next_point(seq_point)
            self._prev_runahead_sequence_points = sequence_points
            self._prev_runahead_base_point = base_point

        if count_cycles:
            # (len(list) may be less than ilimit due to sequence end)
            limit_point = sorted(sequence_points)[:ilimit + 1][-1]
        else:
            limit_point = max(sequence_points)

        # Adjust for future offset and stop point.
        pre_adj_limit = limit_point
        if self.max_future_offset is not None:
            limit_point += self.max_future_offset
            LOG.debug(
                "Runahead (future trigger adjust):"
                f" {pre_adj_limit} -> {limit_point}"
            )
        if self.stop_point and limit_point > self.stop_point:
            limit_point = self.stop_point
            LOG.debug(
                "Runahead (stop point adjust):"
                f" {pre_adj_limit} -> {limit_point} (stop point)"
            )

        LOG.debug(f"Runahead limit: {limit_point}")
        self.runahead_limit_point = limit_point
        return True

    def update_flow_mgr(self):
        flow_nums_seen = set()
        for itask in self.get_tasks():
            flow_nums_seen.update(itask.flow_nums)
        self.flow_mgr.load_from_db(flow_nums_seen)

    def load_abs_outputs_for_restart(self, row_idx, row):
        cycle, name, output = row
        self.abs_outputs_done.add((cycle, name, output))

    def check_task_output(
        self,
        cycle: str,
        task: str,
        output_msg: str,
        flow_nums: 'FlowNums',
    ) -> 'SatisfiedState':
        """Returns truthy if the specified output is satisfied in the DB.

        Args:
            cycle: Cycle point of the task whose output is being checked.
            task: Name of the task whose output is being checked.
            output_msg: The output message to check for.
            flow_nums: Flow numbers of the task whose output is being
                checked. If this is empty it means 'none'; will return False.
        """
        if not flow_nums:
            return False

        for task_outputs, task_flow_nums in (
            self.workflow_db_mgr.pri_dao.select_task_outputs(task, cycle)
        ).items():
            # loop through matching tasks
            # (if task_flow_nums is empty, it means the 'none' flow)
            if flow_nums.intersection(task_flow_nums):
                # BACK COMPAT: In Cylc >8.0.0,<8.3.0, only the task
                #   messages were stored in the DB as a list.
                # from: 8.0.0
                # to: 8.3.0
                outputs: Union[
                    Dict[str, str], List[str]
                ] = json.loads(task_outputs)
                messages = (
                    outputs.values() if isinstance(outputs, dict)
                    else outputs
                )
                return (
                    'satisfied from database'
                    if output_msg in messages
                    else False
                )
        else:
            # no matching entries
            return False

    def load_db_task_pool_for_restart(self, row_idx, row):
        """Load tasks from DB task pool/states/jobs tables.

        Output completion status is loaded from the DB, and tasks recorded
        as submitted or running are polled to confirm their true status.
        Tasks are added to queues again on release from runahead pool.

        Returns:
            Names of platform if attempting to look up that platform
            has led to a PlatformNotFoundError.
        """
        if row_idx == 0:
            LOG.info("LOADING task proxies")
        # Create a task proxy corresponding to this DB entry.
        (cycle, name, flow_nums, flow_wait, is_manual_submit, is_late, status,
         is_held, submit_num, _, platform_name, time_submit, time_run, timeout,
         outputs_str) = row
        try:
            itask = TaskProxy(
                self.tokens,
                self.config.get_taskdef(name),
                get_point(cycle),
                deserialise_set(flow_nums),
                status=status,
                is_held=is_held,
                submit_num=submit_num,
                is_late=bool(is_late),
                flow_wait=bool(flow_wait),
                is_manual_submit=bool(is_manual_submit),
                sequential_xtrigger_labels=(
                    self.xtrigger_mgr.xtriggers.sequential_xtrigger_labels
                ),
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
                # If we get a failure from the platform selection function
                # set task status to submit-failed.
                try:
                    itask.platform = get_platform(platform_name)
                except PlatformLookupError:
                    return platform_name

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
                    itask.state.outputs.set_message_complete(message)
                    self.data_store_mgr.delta_task_output(itask, message)

            if platform_name and status != TASK_STATUS_WAITING:
                itask.summary['platforms_used'][
                    int(submit_num)] = platform_name
            LOG.info(
                f"+ {cycle}/{name} {status}{' (held)' if is_held else ''}")

            # Update prerequisite satisfaction status from DB
            sat = {}
            for prereq_name, prereq_cycle, prereq_output_msg, satisfied in (
                    self.workflow_db_mgr.pri_dao.select_task_prerequisites(
                        cycle, name, flow_nums,
                    )
            ):
                # Prereq satisfaction as recorded in the DB.
                sat[
                    (prereq_cycle, prereq_name, prereq_output_msg)
                ] = satisfied if satisfied != '0' else False

            for itask_prereq in itask.state.prerequisites:
                for key in itask_prereq:
                    if key in sat:
                        itask_prereq[key] = sat[key]
                    else:
                        # This prereq is not in the DB: new dependencies
                        # added to an already-spawned task before restart.
                        # Look through task outputs to see if is has been
                        # satisfied
                        prereq_cycle, prereq_task, prereq_output_msg = key
                        itask_prereq[key] = (
                            self.check_task_output(
                                prereq_cycle,
                                prereq_task,
                                prereq_output_msg,
                                itask.flow_nums,
                            )
                        )

            if itask.state_reset(status, is_runahead=True):
                self.data_store_mgr.delta_task_state(itask)
            self.add_to_pool(itask)

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

    def load_db_task_action_timers(self, row_idx: int, row: Iterable) -> None:
        """Load a task action timer, e.g. event handlers, retry states."""
        if row_idx == 0:
            LOG.info("LOADING task action timers")
        (cycle, name, ctx_key_raw, ctx_raw, delays_raw, num, delay,
         timeout) = row
        tokens = Tokens(
            cycle=cycle,
            task=name,
        )
        id_ = tokens.relative_id
        try:
            # Extract type namedtuple variables from JSON strings
            ctx_key = json.loads(str(ctx_key_raw))
            ctx_data = json.loads(str(ctx_raw))
            known_cls: Type[NamedTuple]
            for known_cls in (
                CustomTaskEventHandlerContext,
                TaskEventMailContext,
                TaskJobLogsRetrieveContext
            ):
                if ctx_data and ctx_data[0] == known_cls.__name__:
                    ctx_args: list = ctx_data[1]
                    if len(ctx_args) > len(known_cls._fields):
                        # BACK COMPAT: no-longer used ctx_type arg
                        # from: Cylc 7
                        # to: 8.3.0
                        ctx_args.pop(1)
                    ctx: tuple = known_cls(*ctx_args)
                    break
            else:  # no break
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
            (handler, event), submit_num = ctx_key
            self.task_events_mgr.add_event_timer(
                EventKey(
                    handler,
                    event,
                    # NOTE: the event "message" is not preserved in the DB so
                    # we use the event as a placeholder
                    event,
                    tokens.duplicate(job=submit_num),
                ),
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
            self.data_store_mgr.delta_task_state(itask)
        if itask.is_ready_to_run():
            # (otherwise waiting on xtriggers etc.)
            self.queue_task(itask)

    def get_or_spawn_task(
        self,
        point: 'PointBase',
        tdef: 'TaskDef',
        flow_nums: 'FlowNums',
        flow_wait: bool = False
    ) -> 'Tuple[Optional[TaskProxy], bool, bool]':
        """Return new or existing task point/name with merged flow_nums.

        Returns:
            tuple - (itask, is_in_pool, is_xtrig_sequential)

            itask:
                The requested task proxy, or None if task does not
                exist or cannot spawn.
            is_in_pool:
                Was the task found in a pool.
            is_xtrig_sequential:
                Is the next task occurrence spawned on xtrigger satisfaction,
                or do all occurrence spawn out to the runahead limit.

        It does not add a spawned task proxy to the pool.
        """
        ntask = self.get_task(point, tdef.name)
        is_in_pool = False
        is_xtrig_sequential = False
        if ntask is None:
            # ntask does not exist: spawn it in the flow.
            ntask = self.spawn_task(
                tdef.name, point, flow_nums, flow_wait=flow_wait
            )
            # if the task was found set xtrigger checking type.
            # otherwise find the xtrigger type if it can't spawn
            # for whatever reason.
            if ntask is not None:
                is_xtrig_sequential = ntask.is_xtrigger_sequential
            elif any(
                xtrig_label in (
                    self.xtrigger_mgr.xtriggers.sequential_xtrigger_labels)
                for sequence, xtrig_labels in tdef.xtrig_labels.items()
                for xtrig_label in xtrig_labels
                if sequence.is_valid(point)
            ):
                is_xtrig_sequential = True
        else:
            # ntask already exists (n=0): merge flows.
            is_in_pool = True
            self.merge_flows(ntask, flow_nums)
            is_xtrig_sequential = ntask.is_xtrigger_sequential
        # ntask may still be None
        return ntask, is_in_pool, is_xtrig_sequential

    def spawn_to_rh_limit(
        self,
        tdef: 'TaskDef',
        point: Optional['PointBase'],
        flow_nums: 'FlowNums',
    ) -> None:
        """Spawn parentless task instances from point to runahead limit.

        Sequentially checked xtriggers will spawn the next occurrence of their
        corresponding tasks. These tasks will keep spawning until they depend
        on any unsatisfied xtrigger of the same sequential behavior, are no
        longer parentless, and/or hit the runahead limit.

        """
        if not flow_nums or point is None:
            # Force-triggered no-flow task.
            # Or called with an invalid next_point.
            return
        if self.runahead_limit_point is None:
            self.compute_runahead()
            if self.runahead_limit_point is None:
                return

        is_xtrig_sequential = False
        while point is not None and (point <= self.runahead_limit_point):
            if tdef.is_parentless(point):
                ntask, is_in_pool, is_xtrig_sequential = (
                    self.get_or_spawn_task(point, tdef, flow_nums)
                )
                if ntask is not None:
                    if not is_in_pool:
                        self.add_to_pool(ntask)
                    self.rh_release_and_queue(ntask)
                if is_xtrig_sequential:
                    break
            point = tdef.next_point(point)

        # Once more for the runahead-limited task (don't release it).
        if not is_xtrig_sequential:
            self.spawn_if_parentless(tdef, point, flow_nums)

    def spawn_if_parentless(self, tdef, point, flow_nums):
        """Spawn a task if parentless, regardless of runahead limit."""
        if flow_nums and point is not None and tdef.is_parentless(point):
            ntask, is_in_pool, _ = self.get_or_spawn_task(
                point, tdef, flow_nums
            )
            if ntask is not None and not is_in_pool:
                self.add_to_pool(ntask)

    def remove(self, itask: 'TaskProxy', reason: Optional[str] = None) -> None:
        """Remove a task from the pool."""

        if itask.state.is_runahead and itask.flow_nums:
            # If removing a parentless runahead-limited task
            # auto-spawn its next instance first.
            self.spawn_if_parentless(
                itask.tdef,
                itask.tdef.next_point(itask.point),
                itask.flow_nums
            )

        msg = f"removed from active task pool: {reason or 'completed'}"

        if itask.is_xtrigger_sequential:
            self.xtrigger_mgr.sequential_spawn_next.discard(itask.identity)
            self.xtrigger_mgr.sequential_has_spawned_next.discard(
                itask.identity
            )

        try:
            del self.active_tasks[itask.point][itask.identity]
        except KeyError:
            pass
        else:
            self.tasks_removed = True
            self.active_tasks_changed = True
            if not self.active_tasks[itask.point]:
                del self.active_tasks[itask.point]
            self.task_queue_mgr.remove_task(itask)
            if itask.tdef.max_future_prereq_offset is not None:
                self.set_max_future_offset()

            # Notify the data-store manager of their removal
            # (the manager uses window boundary tracking for pruning).
            self.data_store_mgr.remove_pool_node(itask.tdef.name, itask.point)
            # Event-driven final update of task_states table.
            # TODO: same for datastore (still updated by scheduler loop)
            self.workflow_db_mgr.put_update_task_state(itask)

            level = logging.DEBUG
            if itask.state(
                TASK_STATUS_PREPARING,
                TASK_STATUS_SUBMITTED,
                TASK_STATUS_RUNNING,
            ):
                level = logging.WARNING
                msg += " - active job orphaned"

            LOG.log(level, f"[{itask}] {msg}")

            # ensure this task is written to the DB before moving on
            # https://github.com/cylc/cylc-flow/issues/6315
            self.workflow_db_mgr.process_queued_ops()

            del itask

            # removing this task could nudge the runahead limit forward
            if self.compute_runahead():
                self.release_runahead_tasks()

    def get_tasks(self) -> List[TaskProxy]:
        """Return a list of task proxies in the task pool."""
        # Cached list only for use internally in this method.
        if self.active_tasks_changed:
            self.active_tasks_changed = False
            self._active_tasks_list = [
                itask
                for itask_id_map in self.active_tasks.values()
                for itask in itask_id_map.values()
            ]
        return self._active_tasks_list

    def get_tasks_by_point(self) -> 'Dict[PointBase, List[TaskProxy]]':
        """Return a map of task proxies by cycle point."""
        return {
            point: list(itask_id_map.values())
            for point, itask_id_map in self.active_tasks.items()
        }

    def get_task(self, point: 'PointBase', name: str) -> Optional[TaskProxy]:
        """Retrieve a task from the pool."""
        rel_id = f'{point}/{name}'
        tasks = self.active_tasks.get(point)
        if tasks:
            return tasks.get(rel_id)
        return None

    def _get_task_by_id(self, id_: str) -> Optional[TaskProxy]:
        """Return pool task by ID if it exists, or None."""
        for itask_ids in self.active_tasks.values():
            if id_ in itask_ids:
                return itask_ids[id_]
        return None

    def queue_task(self, itask: TaskProxy) -> None:
        """Queue a task that is ready to run."""
        if itask.state_reset(is_queued=True):
            self.data_store_mgr.delta_task_state(itask)
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
            self.data_store_mgr.delta_task_state(itask)
            itask.waiting_on_job_prep = True

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
        cycles = list(self.active_tasks)
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

    def reload(self, config: 'WorkflowConfig') -> None:
        self.config = config   # store the updated config
        self.xtrigger_mgr.add_xtriggers(
            self.config.xtrigger_collator, reload=True)
        self._reload_taskdefs()

    def _reload_taskdefs(self) -> None:
        """Reload the definitions of task proxies in the pool.

        Orphaned tasks (whose definitions were removed from the workflow):
        - remove if not active yet
        - if active, leave them but prevent them from spawning children on
          subsequent outputs

        Otherwise: replace task definitions but copy over existing outputs etc.

        self.config should already be updated for the reload.
        """
        self.stop_point = self.config.stop_point or self.config.final_point

        # find any old tasks that have been removed from the workflow
        old_task_name_list = self.task_name_list
        self.task_name_list = self.config.get_task_name_list()
        orphans = [
            task
            for task in old_task_name_list
            if task not in self.task_name_list
        ]

        # adjust the new workflow config to handle the orphans
        self.config.adopt_orphans(orphans)

        LOG.info("Reloading task definitions.")
        tasks = self.get_tasks()
        # Log tasks orphaned by a reload but not currently in the task pool.
        for name in orphans:
            if name not in (itask.tdef.name for itask in tasks):
                LOG.warning("Removed task: '%s'", name)
        for itask in tasks:
            if itask.tdef.name in orphans:
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
                    self.tokens,
                    self.config.get_taskdef(itask.tdef.name),
                    itask.point,
                    itask.flow_nums,
                    itask.state.status,
                    sequential_xtrigger_labels=(
                        self.xtrigger_mgr.xtriggers.sequential_xtrigger_labels
                    ),
                )
                itask.copy_to_reload_successor(
                    new_task,
                    self.check_task_output,
                )
                self._swap_out(new_task)
                self.data_store_mgr.delta_task_prerequisite(new_task)
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
            self.task_name_list,
            self.config.runtime['descendants']
        )

        if self.compute_runahead():
            self.release_runahead_tasks()

        # Now queue all tasks that are ready to run
        for itask in self.get_tasks():
            # Recreate data store elements from task pool.
            self.create_data_store_elements(itask)
            if itask.state.is_queued:
                # Already queued
                continue
            if itask.is_ready_to_run() and not itask.state.is_runahead:
                self.queue_task(itask)

    def set_stop_point(self, stop_point: 'PointBase') -> bool:
        """Set the workflow stop cycle point.

        And reset the runahead limit if less than the stop point.
        """
        if self.stop_point == stop_point:
            LOG.info(f"Stop point unchanged: {stop_point}")
            return False

        LOG.info(f"Setting stop point: {stop_point}")
        self.stop_point = stop_point

        if (
            self.runahead_limit_point is not None
            and self.runahead_limit_point > stop_point
        ):
            self.runahead_limit_point = stop_point
            # Now handle existing waiting tasks (e.g. xtriggered).
            for itask in self.get_tasks():
                if (
                    itask.point > stop_point
                    and itask.state(TASK_STATUS_WAITING)
                    and itask.state_reset(is_runahead=True)
                ):
                    self.data_store_mgr.delta_task_state(itask)
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
            # preparing tasks get reset to waiting on restart
            for itask in self.get_tasks()
        )

    def warn_stop_orphans(self) -> None:
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

        for id_key in self.task_events_mgr._event_timers:
            LOG.warning(
                f"{id_key.tokens.relative_id}:"
                " incomplete task event handler"
                f" {(id_key.handler, id_key.event)}"
            )

    def log_incomplete_tasks(self) -> bool:
        """Log finished but incomplete tasks; return True if there any."""
        incomplete = []
        for itask in self.get_tasks():
            if not itask.state(*TASK_STATUSES_FINAL):
                continue
            if not itask.state.outputs.is_complete():
                incomplete.append(
                    (
                        itask.identity,
                        itask.state.outputs.format_completion_status(
                            ansimarkup=1
                        ),
                    )
                )

        if incomplete:
            LOG.error(
                "Incomplete tasks:\n"
                + "\n".join(
                    f"* {id_} did not complete the required outputs:"
                    f"\n{indent(outputs, '  ')}"
                    for id_, outputs in incomplete
                )
            )
            return True
        return False

    def log_unsatisfied_prereqs(self) -> bool:
        """Log unsatisfied prerequisites in the pool.

        Return True if any, ignoring:
            - prerequisites beyond the stop point
            - dependence on tasks beyond the stop point
            (can be caused by future triggers)
        """
        unsat: Dict[str, List[str]] = {}
        for itask in self.get_tasks():
            task_point = itask.point
            if self.stop_point and task_point > self.stop_point:
                continue
            for pr in itask.state.get_unsatisfied_prerequisites():
                if self.stop_point and get_point(pr.point) > self.stop_point:
                    continue
                if itask.identity not in unsat:
                    unsat[itask.identity] = []
                unsat[itask.identity].append(
                    f"{pr.get_id()}:"
                    f"{self.config.get_taskdef(pr.task).get_output(pr.output)}"
                )
        if unsat:
            LOG.warning(
                "Partially satisfied prerequisites:\n"
                + "\n".join(
                    f"  * {id_} is waiting on {others}"
                    for id_, others in unsat.items()
                )
            )
            return True
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
                # (avoid waiting pre-spawned absolute-triggered tasks:)
                and itask.prereqs_are_satisfied()
            ) for itask in self.get_tasks()
        ):
            return False

        incomplete = self.log_incomplete_tasks()
        unsatisfied = self.log_unsatisfied_prereqs()
        return (incomplete or unsatisfied)

    def hold_active_task(self, itask: TaskProxy) -> None:
        if itask.state_reset(is_held=True):
            self.data_store_mgr.delta_task_state(itask)
        self.tasks_to_hold.add((itask.tdef.name, itask.point))
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)

    def release_held_active_task(self, itask: TaskProxy) -> None:
        if itask.state_reset(is_held=False):
            self.data_store_mgr.delta_task_state(itask)
            if (not itask.state.is_runahead) and itask.is_ready_to_run():
                self.queue_task(itask)
        self.tasks_to_hold.discard((itask.tdef.name, itask.point))
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)

    def set_hold_point(self, point: 'PointBase') -> None:
        """Set the point after which all tasks must be held."""
        self.hold_point = point
        for itask in self.get_tasks():
            if itask.point > point:
                self.hold_active_task(itask)
        self.workflow_db_mgr.put_workflow_hold_cycle_point(point)

    def hold_tasks(self, items: Iterable[str]) -> int:
        """Hold tasks with IDs matching the specified items."""
        # Hold active tasks:
        itasks, inactive_tasks, unmatched = self.filter_task_proxies(
            items,
            warn_no_active=False,
            inactive=True,
        )
        for itask in itasks:
            self.hold_active_task(itask)
        # Set inactive tasks to be held:
        for name, cycle in inactive_tasks:
            self.data_store_mgr.delta_task_held(name, cycle, True)
        self.tasks_to_hold.update(inactive_tasks)
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)
        LOG.debug(f"Tasks to hold: {self.tasks_to_hold}")
        return len(unmatched)

    def release_held_tasks(self, items: Iterable[str]) -> int:
        """Release held tasks with IDs matching any specified items."""
        # Release active tasks:
        itasks, inactive_tasks, unmatched = self.filter_task_proxies(
            items,
            warn_no_active=False,
            inactive=True,
        )
        for itask in itasks:
            self.release_held_active_task(itask)
        # Unhold inactive tasks:
        for name, cycle in inactive_tasks:
            self.data_store_mgr.delta_task_held(name, cycle, False)
        self.tasks_to_hold.difference_update(inactive_tasks)
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)
        LOG.debug(f"Tasks to hold: {self.tasks_to_hold}")
        return len(unmatched)

    def release_hold_point(self) -> None:
        """Unset the workflow hold point and release all held active tasks."""
        self.hold_point = None
        for itask in self.get_tasks():
            self.release_held_active_task(itask)
        self.tasks_to_hold.clear()
        self.workflow_db_mgr.put_tasks_to_hold(self.tasks_to_hold)
        self.workflow_db_mgr.put_workflow_hold_cycle_point(None)

    def check_abort_on_task_fails(self):
        """Check whether workflow should abort on task failure.

        Return True if a task failed and `--abort-if-any-task-fails` was given.
        """
        return self.abort_task_failed

    def spawn_on_output(self, itask: TaskProxy, output: str) -> None:
        """Spawn child-tasks of given output, into the pool.

        Remove the parent task from the pool if complete.

        Called by task event manager on receiving output messages, and after
        forced setting of task outputs (in this case the parent task could
        be transient, i.e. not in the pool).

        Also set the abort-on-task-failed flag if necessary.

        If not flowing on, update existing children but don't spawn new ones
        (unless manually forced to spawn with no flow number).

        If an absolute output is completed update the store of completed abs
        outputs, and update the prerequisites of every instance of the child
        in the pool. (The self.spawn method uses the store of completed abs
        outputs to satisfy any tasks with absolute prerequisites).

        Args:
            output: output to spawn on.

        """
        if (
            output == TASK_OUTPUT_FAILED
            and self.expected_failed_tasks is not None
            and itask.identity not in self.expected_failed_tasks
        ):
            self.abort_task_failed = True

        children = []
        if itask.flow_nums:
            with suppress(KeyError):
                children = itask.graph_children[output]

        if itask.flow_wait and children:
            LOG.warning(
                f"[{itask}] not spawning on {output}: flow wait requested")
            self.remove_if_complete(itask, output)
            return

        suicide = []
        for c_name, c_point, is_abs in children:

            if is_abs:
                self.abs_outputs_done.add(
                    (str(itask.point), itask.tdef.name, output))
                self.workflow_db_mgr.put_insert_abs_output(
                    str(itask.point), itask.tdef.name, output)
                self.workflow_db_mgr.process_queued_ops()

            c_task = self._get_task_by_id(quick_relative_id(c_point, c_name))
            in_pool = c_task is not None

            if c_task is not None and c_task != itask:
                # (Avoid self-suicide: A => !A)
                self.merge_flows(c_task, itask.flow_nums)
            elif c_task is None and itask.flow_nums:
                # If child is not in the pool already, and parent belongs to a
                # flow (so it can spawn children), and parent is not waiting
                # for an upcoming flow merge before spawning ... then spawn it.
                c_task = self.spawn_task(c_name, c_point, itask.flow_nums)

            if c_task is not None:
                # Have child task, update its prerequisites.
                if is_abs:
                    tasks, *_ = self.filter_task_proxies(
                        [f'*/{c_name}'],
                        warn_no_active=False,
                    )
                    if c_task not in tasks:
                        tasks.append(c_task)
                else:
                    tasks = [c_task]

                for t in tasks:
                    t.satisfy_me([itask.tokens.duplicate(task_sel=output)])
                    self.data_store_mgr.delta_task_prerequisite(t)
                    if not in_pool:
                        self.add_to_pool(t)

                    if (
                        self.runahead_limit_point is not None
                        and t.point <= self.runahead_limit_point
                    ):
                        self.rh_release_and_queue(t)

                    # Event-driven suicide.
                    if (
                        t.state.suicide_prerequisites and
                        t.state.suicide_prerequisites_all_satisfied()
                    ):
                        suicide.append(t)

        for c_task in suicide:
            self.remove(c_task, self.__class__.SUICIDE_MSG)

        if suicide:
            # Update DB now in case of very quick respawn attempt.
            # See https://github.com/cylc/cylc-flow/issues/6066
            self.workflow_db_mgr.process_queued_ops()

        self.remove_if_complete(itask, output)

    def remove_if_complete(
        self, itask: TaskProxy, output: Optional[str] = None
    ) -> bool:
        """Remove a finished task if required outputs are complete.

        Return True if removed else False.

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
        if not itask.state(*TASK_STATUSES_FINAL):
            # can't be complete
            return False

        if itask.identity == self.stop_task_id:
            self.stop_task_finished = True

        if cylc.flow.flags.cylc7_back_compat:
            ret = False
            if not itask.state(TASK_STATUS_FAILED, TASK_OUTPUT_SUBMIT_FAILED):
                self.remove(itask)
                ret = True
            # Recompute runahead either way; failed tasks don't count in C7.
            if self.compute_runahead():
                self.release_runahead_tasks()
            return ret

        if not itask.state.outputs.is_complete():
            # Keep incomplete tasks in the pool.
            if output in TASK_STATUSES_FINAL:
                # Log based on the output, not the state, to avoid warnings
                # due to use of "cylc set" to set internal outputs on an
                # already-finished task.
                LOG.warning(
                    f"[{itask}] did not complete the required outputs:\n"
                    + itask.state.outputs.format_completion_status(
                        ansimarkup=1
                    )
                )
            return False

        self.remove(itask)
        if self.compute_runahead():
            self.release_runahead_tasks()
        return True

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
        if not itask.flow_nums:
            return

        for _trigger, message, is_completed in itask.state.outputs:
            if completed_only and not is_completed:
                continue
            try:
                children = itask.graph_children[message]
            except KeyError:
                continue

            for c_name, c_point, _ in children:
                c_taskid = Tokens(
                    cycle=str(c_point),
                    task=c_name,
                ).relative_id
                c_task = self._get_task_by_id(c_taskid)
                if c_task is not None:
                    # already spawned
                    continue

                c_task = self.spawn_task(c_name, c_point, itask.flow_nums)
                if c_task is None:
                    # not spawnable
                    continue
                if completed_only:
                    c_task.satisfy_me(
                        [itask.tokens.duplicate(task_sel=message)]
                    )
                    self.data_store_mgr.delta_task_prerequisite(c_task)
                self.add_to_pool(c_task)
                if (
                    self.runahead_limit_point is not None
                    and c_task.point <= self.runahead_limit_point
                ):
                    self.rh_release_and_queue(c_task)

    def can_be_spawned(self, name: str, point: 'PointBase') -> bool:
        """Return True if a point/name is within graph bounds."""

        if name not in self.config.taskdefs:
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

        if self.config.final_point and point > self.config.final_point:
            # Only happens on manual trigger beyond FCP
            LOG.debug(
                'Not spawning %s/%s: beyond final cycle point', point, name)
            return False

        # Is it on-sequence and within recurrence bounds.
        if not self.config.get_taskdef(name).is_valid_point(point):
            LOG.warning(
                self.ERR_PREFIX_TASK_NOT_ON_SEQUENCE.format(
                    name, point
                )
            )
            return False

        return True

    def _get_task_history(
        self, name: str, point: 'PointBase', flow_nums: Set[int]
    ) -> Tuple[int, Optional[str], bool]:
        """Get submit_num, status, flow_wait for point/name in flow_nums.

        Args:
            name: task name
            point: task cycle point
            flow_nums: task flow numbers

        Returns:
           (submit_num, status, flow_wait)
           If no matching history, status will be None

        """
        submit_num: int = 0
        status: Optional[str] = None
        flow_wait = False

        info = self.workflow_db_mgr.pri_dao.select_prev_instances(
            name, str(point)
        )
        with suppress(ValueError):
            submit_num = max(s[0] for s in info)

        for _snum, f_wait, old_fnums, old_status in info:
            if set.intersection(flow_nums, old_fnums):
                # matching flows
                status = old_status
                flow_wait = f_wait
                if status in TASK_STATUSES_FINAL:
                    # task finished
                    break
                # Else continue: there may be multiple entries with flow
                # overlap due to merges (they'll have have same snum and
                # f_wait); keep going to find the finished one, if any.

        return submit_num, status, flow_wait

    def _load_historical_outputs(self, itask: 'TaskProxy') -> None:
        """Load a task's historical outputs from the DB."""
        info = self.workflow_db_mgr.pri_dao.select_task_outputs(
            itask.tdef.name, str(itask.point))
        if not info:
            # task never ran before
            self.db_add_new_flow_rows(itask)
        else:
            flow_seen = False
            for outputs_str, fnums in info.items():
                # (if fnums is empty, it means the 'none' flow)
                if itask.flow_nums.intersection(fnums):
                    # DB row has overlap with itask's flows
                    flow_seen = True
                    # BACK COMPAT: In Cylc >8.0.0,<8.3.0, only the task
                    #   messages were stored in the DB as a list.
                    # from: 8.0.0
                    # to: 8.3.0
                    outputs: Union[
                        Dict[str, str], List[str]
                    ] = json.loads(outputs_str)
                    if isinstance(outputs, dict):
                        # {trigger: message} - match triggers, not messages.
                        # DB may record forced completion rather than message.
                        for trigger in outputs.keys():
                            itask.state.outputs.set_trigger_complete(trigger)
                    else:
                        # [message] - always the full task message
                        for msg in outputs:
                            itask.state.outputs.set_message_complete(msg)
            if not flow_seen:
                # itask never ran before in its assigned flows
                self.db_add_new_flow_rows(itask)

    def spawn_task(
        self,
        name: str,
        point: 'PointBase',
        flow_nums: Set[int],
        flow_wait: bool = False,
    ) -> Optional[TaskProxy]:
        """Return a new task proxy for the given flow if possible.

        We need to hit the DB for:
        - submit number
        - task status
        - flow-wait
        - completed outputs (e.g. via "cylc set")

        If history records a final task status (for this flow):
        - if not flow wait, don't spawn (return None)
        - if flow wait, don't spawn (return None) but do spawn children
        - if outputs are incomplete, don't auto-rerun it (return None)

        Otherwise, spawn the task and load any completed outputs.

        """
        submit_num, prev_status, prev_flow_wait = (
            self._get_task_history(name, point, flow_nums)
        )

        # Create the task proxy with any completed outputs loaded.
        itask = self._get_task_proxy_db_outputs(
            point,
            self.config.get_taskdef(name),
            flow_nums,
            status=prev_status or TASK_STATUS_WAITING,
            submit_num=submit_num,
            flow_wait=flow_wait,
        )
        if itask is None:
            return None

        if (
            prev_status is not None
            and not itask.state.outputs.get_completed_outputs()
        ):
            # If itask has any history in this flow but no completed outputs
            # we can infer it has just been deliberately removed (N.B. not
            # by `cylc remove`), so don't immediately respawn it.
            # TODO (follow-up work):
            # - this logic fails if task removed after some outputs completed
            LOG.debug(f"Not respawning {point}/{name} - task was removed")
            return None

        if prev_status in TASK_STATUSES_FINAL:
            # Task finished previously.
            msg = f"[{point}/{name}:{prev_status}] already finished"
            if itask.is_complete():
                msg += " and completed"
                itask.transient = True
            else:
                # revive as incomplete.
                msg += " incomplete"

            LOG.info(
                f"{msg} {repr_flow_nums(flow_nums, full=True)})"
            )
            if prev_flow_wait:
                self._spawn_after_flow_wait(itask)

            if itask.transient:
                return None

        if not itask.transient:
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

            # Don't add to pool if it depends on a task beyond the stop point.
            #   "foo; foo[+P1] & bar => baz"
            # Here, in the final cycle bar wants to spawn baz, but that would
            # stall because baz also depends on foo after the final point.
            if self.stop_point and itask.point <= self.stop_point:
                for pct in itask.state.prerequisites_get_target_points():
                    if pct > self.stop_point:
                        LOG.warning(
                            f"[{itask}] not spawned: a prerequisite is beyond"
                            f" the workflow stop point ({self.stop_point})"
                        )
                        return None

            # Satisfy any absolute triggers.
            if (
                itask.tdef.has_abs_triggers
                and itask.state.prerequisites_are_not_all_satisfied()
            ):
                itask.satisfy_me([
                    Tokens(cycle=cycle, task=task, task_sel=output)
                    for cycle, task, output in self.abs_outputs_done
                ])

        self.db_add_new_flow_rows(itask)
        return itask

    def _spawn_after_flow_wait(self, itask: TaskProxy) -> None:
        LOG.info(f"[{itask}] spawning outputs after flow-wait")
        self.spawn_on_all_outputs(itask, completed_only=True)
        # update flow wait status in the DB
        itask.flow_wait = False
        # itask.flow_nums = orig_fnums
        self.workflow_db_mgr.put_update_task_flow_wait(itask)
        return None

    def _get_task_proxy_db_outputs(
        self,
        point: 'PointBase',
        taskdef: 'TaskDef',
        flow_nums: 'FlowNums',
        status: str = TASK_STATUS_WAITING,
        flow_wait: bool = False,
        transient: bool = False,
        is_manual_submit: bool = False,
        submit_num: int = 0,
    ) -> Optional['TaskProxy']:
        """Spawn a task, update outputs from DB."""

        if not self.can_be_spawned(taskdef.name, point):
            return None

        itask = TaskProxy(
            self.tokens,
            taskdef,
            point,
            flow_nums,
            status=status,
            flow_wait=flow_wait,
            submit_num=submit_num,
            transient=transient,
            is_manual_submit=is_manual_submit,
            sequential_xtrigger_labels=(
                self.xtrigger_mgr.xtriggers.sequential_xtrigger_labels
            ),
        )
        # Update it with outputs that were already completed.
        self._load_historical_outputs(itask)
        return itask

    def _standardise_prereqs(
        self, prereqs: 'List[str]'
    ) -> 'Dict[Tokens, str]':
        """Convert prerequisites to a map of task messages: outputs.

        (So satsify_me logs failures)

        """
        _prereqs = {}
        for prereq in prereqs:
            pre = Tokens(prereq, relative=True)
            # add implicit "succeeded"; convert "succeed" to "succeeded" etc.
            output = TaskTrigger.standardise_name(
                pre['task_sel'] or TASK_OUTPUT_SUCCEEDED)
            # Convert outputs to task messages.
            try:
                msg = self.config.get_taskdef(
                    pre['task']
                ).outputs[output][0]
                cycle = standardise_point_string(pre['cycle'])
            except KeyError:
                # The task does not have this output.
                LOG.warning(
                    f"output {pre.relative_id_with_selectors} not found")
                continue
            except WorkflowConfigError as exc:
                LOG.warning(
                    f'Invalid prerequisite task name:\n{exc.args[0]}')
            except PointParsingError as exc:
                LOG.warning(
                    f'Invalid prerequisite cycle point:\n{exc.args[0]}')
            else:
                _prereqs[pre.duplicate(task_sel=msg, cycle=cycle)] = prereq
        return _prereqs

    def _standardise_outputs(
        self, point: 'PointBase', tdef: 'TaskDef', outputs: List[str]
    ) -> List[str]:
        """Convert output names to task output messages."""
        _outputs = []
        for out in outputs:
            # convert "succeed" to "succeeded" etc.
            output = TaskTrigger.standardise_name(out)
            try:
                msg = tdef.outputs[output][0]
            except KeyError:
                LOG.warning(f"output {point}/{tdef.name}:{output} not found")
                continue
            _outputs.append(msg)
        return _outputs

    def set_prereqs_and_outputs(
        self,
        items: Iterable[str],
        outputs: List[str],
        prereqs: List[str],
        flow: List[str],
        flow_wait: bool = False,
        flow_descr: Optional[str] = None
    ):
        """Set prerequisites or outputs of target tasks.

        Default: set all required outputs.

        Set prerequisites:
        - spawn the task (if not spawned)
        - update its prerequisites

        Set outputs:
        - update task outputs in the DB
        - (implied outputs are handled by the event manager)
        - spawn children of the outputs (if not spawned)
        - update the child prerequisites

        Task matching restrictions (for now):
        - globs (cycle and name) only match in the pool
        - inactive tasks must be specified individually
        - family names are not expanded to members

        Uses a transient task proxy to spawn children. (Even if parent was
        previously spawned in this flow its children might not have been).

        Note transient tasks are a subset of forced tasks (you can
        force-trigger a task that is already in the pool).

        A forced output cannot cause a state change to submitted or running,
        but it can complete a task so that it doesn't need to run.

        Args:
            items: task ID match patterns
            prereqs: prerequisites to set
            outputs: outputs to set
            flow: flow numbers for spawned or merged tasks
            flow_wait: wait for flows to catch up before continuing
            flow_descr: description of new flow

        """
        # Get matching pool tasks and inactive task definitions.
        itasks, inactive_tasks, unmatched = self.filter_task_proxies(
            items,
            inactive=True,
            warn_no_active=False,
        )

        flow_nums = self._get_flow_nums(flow, flow_descr)

        # Set existing task proxies.
        for itask in itasks:
            if flow == ['none'] and itask.flow_nums != set():
                LOG.error(
                    f"[{itask}] ignoring 'flow=none' set: task already has"
                    f" {repr_flow_nums(itask.flow_nums, full=True)}"
                )
                continue
            self.merge_flows(itask, flow_nums)
            if prereqs:
                self._set_prereqs_itask(itask, prereqs, flow_nums)
            else:
                # Spawn as if seq xtrig of parentless task was satisfied,
                # with associated task producing these outputs.
                self.check_spawn_psx_task(itask)
                self._set_outputs_itask(itask, outputs)

        # Spawn and set inactive tasks.
        if not flow:
            # default: assign to all active flows
            flow_nums = self._get_active_flow_nums()
        for name, point in inactive_tasks:
            tdef = self.config.get_taskdef(name)
            if prereqs:
                self._set_prereqs_tdef(
                    point, tdef, prereqs, flow_nums, flow_wait)
            else:
                trans = self._get_task_proxy_db_outputs(
                    point, tdef, flow_nums,
                    flow_wait=flow_wait, transient=True
                )
                if trans is not None:
                    self._set_outputs_itask(trans, outputs)

        if self.compute_runahead():
            self.release_runahead_tasks()

    def _set_outputs_itask(
        self,
        itask: 'TaskProxy',
        outputs: List[str],
    ) -> None:
        """Set requested outputs on a task proxy and spawn children."""
        if not outputs:
            outputs = list(itask.state.outputs.iter_required_messages())
        else:
            outputs = self._standardise_outputs(
                itask.point, itask.tdef, outputs
            )

        for output in sorted(outputs, key=itask.state.outputs.output_sort_key):
            if itask.state.outputs.is_message_complete(output):
                LOG.info(f"output {itask.identity}:{output} completed already")
                continue
            self.task_events_mgr.process_message(
                itask, logging.INFO, output, forced=True)

        if not itask.state(TASK_STATUS_WAITING):
            # Can't be runahead limited or queued.
            itask.state_reset(is_runahead=False, is_queued=False)
            self.task_queue_mgr.remove_task(itask)

        self.data_store_mgr.delta_task_state(itask)
        self.data_store_mgr.delta_task_outputs(itask)
        self.workflow_db_mgr.put_update_task_state(itask)
        self.workflow_db_mgr.put_update_task_outputs(itask)
        self.workflow_db_mgr.process_queued_ops()

    def _set_prereqs_itask(
        self,
        itask: 'TaskProxy',
        prereqs: 'List[str]',
        flow_nums: 'Set[int]',
    ) -> bool:
        """Set prerequisites on a task proxy.

        Prerequisite format: "cycle/task:output" or "all".

        Return True if any prereqs are valid, else False.

        """
        if prereqs == ["all"]:
            itask.state.set_prerequisites_all_satisfied()
        else:
            # Attempt to set the given presrequisites.
            # Log any that aren't valid for the task.
            presus = self._standardise_prereqs(prereqs)
            unmatched = itask.satisfy_me(presus.keys(), forced=True)
            for task_msg in unmatched:
                LOG.warning(
                    f"{itask.identity} does not depend on"
                    f' "{presus[task_msg]}"'
                )
            if len(unmatched) == len(prereqs):
                # No prereqs matched.
                return False
        if (
            self.runahead_limit_point is not None
            and itask.point <= self.runahead_limit_point
        ):
            self.rh_release_and_queue(itask)
        self.data_store_mgr.delta_task_prerequisite(itask)
        return True

    def _set_prereqs_tdef(
        self, point, taskdef, prereqs, flow_nums, flow_wait
    ):
        """Spawn an inactive task and set prerequisites on it."""

        itask = self.spawn_task(
            taskdef.name, point, flow_nums, flow_wait=flow_wait
        )
        if itask is None:
            return
        if self._set_prereqs_itask(itask, prereqs, flow_nums):
            self.add_to_pool(itask)

    def _get_active_flow_nums(self) -> 'FlowNums':
        """Return all active flow numbers.

        If there are no active flows (e.g. on restarting a completed workflow)
        return the most recent active flows.
        Or, if there are no flows in the workflow history (e.g. after
        `cylc remove`), return flow=1.

        """
        return (
            set().union(*(itask.flow_nums for itask in self.get_tasks()))
            or self.workflow_db_mgr.pri_dao.select_latest_flow_nums()
            or {1}
        )

    def remove_tasks(
        self, items: Iterable[str], flow_nums: Optional['FlowNums'] = None
    ) -> None:
        """Remove tasks from the pool (forced by command).

        Args:
            items: Relative IDs or globs.
            flow_nums: Flows to remove the tasks from. If empty or None, it
                means 'all'.
        """
        active, inactive, _unmatched = self.filter_task_proxies(
            items, warn_no_active=False, inactive=True
        )
        if not (active or inactive):
            return

        if flow_nums is None:
            flow_nums = set()
        # Mapping of task IDs to removed flow numbers:
        removed: Dict[str, FlowNums] = {}
        not_removed: Set[str] = set()

        for itask in active:
            fnums_to_remove = itask.match_flows(flow_nums)
            if not fnums_to_remove:
                not_removed.add(itask.identity)
                continue
            removed[itask.identity] = fnums_to_remove
            if fnums_to_remove == itask.flow_nums:
                # Need to remove the task from the pool.
                # Spawn next occurrence of xtrigger sequential task (otherwise
                # this would not happen after removing this occurrence):
                self.check_spawn_psx_task(itask)
                self.remove(itask, 'request')
            else:
                itask.flow_nums.difference_update(fnums_to_remove)

        matched_task_ids = {
            *removed.keys(),
            *(quick_relative_id(cycle, task) for task, cycle in inactive),
        }

        # Unset any prereqs naturally satisfied by these tasks
        # (do not unset those satisfied by `cylc set --pre`):
        for itask in self.get_tasks():
            fnums_to_remove = itask.match_flows(flow_nums)
            if not fnums_to_remove:
                continue
            for prereq in (
                *itask.state.prerequisites,
                *itask.state.suicide_prerequisites,
            ):
                for msg in prereq.naturally_satisfied_dependencies():
                    id_ = msg.get_id()
                    if id_ in matched_task_ids:
                        prereq[msg] = False
                        if id_ not in removed:
                            removed[id_] = fnums_to_remove

        # Remove from DB tables:
        for id_ in matched_task_ids:
            point, name = id_.split('/', 1)
            db_removed_fnums = self.workflow_db_mgr.remove_task_from_flows(
                point, name, flow_nums
            )
            if db_removed_fnums:
                removed.setdefault(id_, set()).update(db_removed_fnums)

        if removed:
            tasks_str = ', '.join(
                sorted(
                    f"{task} {repr_flow_nums(fnums, full=True)}"
                    for task, fnums in removed.items()
                )
            )
            LOG.info(f"Removed task(s): {tasks_str}")

        not_removed.update(matched_task_ids.difference(removed))
        if not_removed:
            fnums_str = (
                repr_flow_nums(flow_nums, full=True) if flow_nums else ''
            )
            LOG.warning(
                "Task(s) not removable: "
                f"{', '.join(sorted(not_removed))} {fnums_str}"
            )

        if removed and self.compute_runahead():
            self.release_runahead_tasks()

    def _get_flow_nums(
        self,
        flow: List[str],
        meta: Optional[str] = None,
    ) -> Set[int]:
        """Return flow numbers corresponding to user command options.

        Arg should have been validated already during command validation.

        In the default case (--flow option not provided), stick with the
        existing flows (so return empty set) - NOTE this only applies for
        active tasks.

        """
        if flow == [FLOW_NONE]:
            return set()
        if flow == [FLOW_ALL]:
            return self._get_active_flow_nums()
        if flow == [FLOW_NEW]:
            return {self.flow_mgr.get_flow_num(meta=meta)}
        # else specific flow numbers:
        return {
            self.flow_mgr.get_flow_num(flow_num=int(n), meta=meta)
            for n in flow
        }

    def _force_trigger(self, itask):
        """Assumes task is in the pool"""
        # TODO is this flag still needed, and consistent with "cylc set"?
        itask.is_manual_submit = True
        itask.reset_try_timers()
        if itask.state_reset(TASK_STATUS_WAITING):
            # (could also be unhandled failed)
            self.data_store_mgr.delta_task_state(itask)
        # (No need to set prerequisites satisfied here).
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
        # Task may be set running before xtrigger is satisfied,
        # if so check/spawn if xtrigger sequential.
        self.check_spawn_psx_task(itask)

    def force_trigger_tasks(
        self, items: Iterable[str],
        flow: List[str],
        flow_wait: bool = False,
        flow_descr: Optional[str] = None
    ):
        """Force a task to trigger (user command).

        Always run the task, even if a previous run was flow-waited.

        If the task did not run before in the flow:
          - run it, and spawn on outputs unless flow-wait is set.
            (but load the previous outputs from the DB)

        Else if the task ran before in the flow:
          - load previous outputs
          If the previous run was not flow-wait
            - run it, and try to spawn on outputs
          Else if the previous run was flow-wait:
            - just spawn (if not already spawned in this flow)
              unless flow-wait is set.

        """
        # Get matching tasks proxies, and matching inactive task IDs.
        existing_tasks, inactive_ids, unmatched = self.filter_task_proxies(
            items, inactive=True, warn_no_active=False,
        )

        flow_nums = self._get_flow_nums(flow, flow_descr)

        # Trigger active tasks.
        for itask in existing_tasks:
            if flow == ['none'] and itask.flow_nums != set():
                LOG.error(
                    f"[{itask}] ignoring 'flow=none' trigger: task already has"
                    f" {repr_flow_nums(itask.flow_nums, full=True)}"
                )
                continue
            if itask.state(TASK_STATUS_PREPARING, *TASK_STATUSES_ACTIVE):
                LOG.error(f"[{itask}] ignoring trigger - already active")
                continue
            self.merge_flows(itask, flow_nums)
            self._force_trigger(itask)

        # Spawn and trigger inactive tasks.
        if not flow:
            # default: assign to all active flows
            flow_nums = self._get_active_flow_nums()
        for name, point in inactive_ids:
            if not self.can_be_spawned(name, point):
                continue
            submit_num, _, prev_fwait = (
                self._get_task_history(name, point, flow_nums)
            )
            itask = TaskProxy(
                self.tokens,
                self.config.get_taskdef(name),
                point,
                flow_nums,
                flow_wait=flow_wait,
                submit_num=submit_num,
                sequential_xtrigger_labels=(
                    self.xtrigger_mgr.xtriggers.sequential_xtrigger_labels
                ),
            )
            if itask is None:
                continue

            self.db_add_new_flow_rows(itask)

            if prev_fwait:
                # update completed outputs from the DB
                self._load_historical_outputs(itask)

            # run it (or run it again for incomplete flow-wait)
            self.add_to_pool(itask)
            self._force_trigger(itask)

    def spawn_parentless_sequential_xtriggers(self):
        """Spawn successor(s) of parentless wall clock satisfied tasks."""
        while self.xtrigger_mgr.sequential_spawn_next:
            taskid = self.xtrigger_mgr.sequential_spawn_next.pop()
            itask = self._get_task_by_id(taskid)
            self.check_spawn_psx_task(itask)

    def check_spawn_psx_task(self, itask: 'TaskProxy') -> None:
        """Check and spawn parentless sequential xtriggered task (psx)."""
        # Will spawn out to RH limit or next parentless clock trigger
        # or non-parentless.
        if (
            itask.is_xtrigger_sequential
            and (
                itask.identity not in
                self.xtrigger_mgr.sequential_has_spawned_next
            )
        ):
            self.xtrigger_mgr.sequential_has_spawned_next.add(
                itask.identity
            )
            self.spawn_to_rh_limit(
                itask.tdef,
                itask.tdef.next_point(itask.point),
                itask.flow_nums
            )

    def clock_expire_tasks(self):
        """Expire any tasks past their clock-expiry time."""
        for itask in self.get_tasks():
            if (
                # force triggered tasks can not clock-expire
                # see proposal point 10:
                # https://cylc.github.io/cylc-admin/proposal-optional-output-extension.html#proposal
                not itask.is_manual_submit

                # only waiting tasks can clock-expire
                # see https://github.com/cylc/cylc-flow/issues/6025
                # (note retrying tasks will be in the waiting state)
                and itask.state(TASK_STATUS_WAITING)

                # check if this task is clock expired
                and itask.clock_expire()
            ):
                self.task_queue_mgr.remove_task(itask)
                self.task_events_mgr.process_message(
                    itask,
                    logging.WARNING,
                    TASK_OUTPUT_EXPIRED,
                )

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
        for itask in self.get_tasks():
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
                    # Don't spawn successor if the task is parentless.
                    self.remove(itask, "flow stopped")

        if self.compute_runahead():
            self.release_runahead_tasks()

    def log_task_pool(self, log_lvl=logging.DEBUG):
        """Log content of task pool, for debugging."""
        LOG.log(
            log_lvl,
            "\n".join(
                f"* {itask}" for itask in self.get_tasks()
            )
        )

    def filter_task_proxies(
        self,
        ids: Iterable[str],
        warn_no_active: bool = True,
        inactive: bool = False,
    ) -> 'Tuple[List[TaskProxy], Set[Tuple[str, PointBase]], List[str]]':
        """Return task proxies that match names, points, states in items.

        Args:
            ids:
                ID strings.
            warn_no_active:
                Whether to log a warning if no matching active tasks are found.
            inactive:
                If True, unmatched IDs will be checked against taskdefs
                and cycle, and any matches will be returned in the second
                return value, provided that the ID:

                * Specifies a cycle point.
                * Is not a pattern. (e.g. `*/foo`).
                * Does not contain a state selector (e.g. `:failed`).

        Returns:
            (matched, inactive_matched, unmatched)

        """
        matched, unmatched = filter_ids(
            self.active_tasks,
            ids,
            warn=warn_no_active,
        )
        inactive_matched: 'Set[Tuple[str, PointBase]]' = set()
        if inactive and unmatched:
            inactive_matched, unmatched = self.match_inactive_tasks(
                unmatched
            )

        return matched, inactive_matched, unmatched

    def match_inactive_tasks(
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
                    tokens = tokens.duplicate(task='*')
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
                tokens = tokens.duplicate(task='*')
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
        if not flow_nums or (flow_nums == itask.flow_nums):
            # Don't do anything if:
            # 1. merging from a no-flow task, or
            # 2. same flow (no merge needed); can arise
            # downstream of an AND trigger (if "A & B => C"
            # and A spawns C first, B will find C is already in the pool),
            # and via suicide triggers ("A =>!A": A tries to spawn itself).
            return

        merge_with_no_flow = not itask.flow_nums

        itask.merge_flows(flow_nums)
        self.data_store_mgr.delta_task_flow_nums(itask)

        # Merged tasks get a new row in the db task_states table.
        self.db_add_new_flow_rows(itask)

        if (
            itask.state(*TASK_STATUSES_FINAL)
            and not itask.state.outputs.is_complete()
        ):
            # Re-queue incomplete task to run again in the merged flow.
            LOG.info(f"[{itask}] incomplete task absorbed by new flow.")
            itask.state_reset(TASK_STATUS_WAITING)
            self.queue_task(itask)
            self.data_store_mgr.delta_task_state(itask)

        elif merge_with_no_flow or itask.flow_wait:
            # 2. Retro-spawn on completed outputs and continue as merged flow.
            LOG.info(f"[{itask}] spawning on pre-merge outputs")
            itask.flow_wait = False
            self.spawn_on_all_outputs(itask, completed_only=True)
            self.spawn_to_rh_limit(
                itask.tdef, itask.next_point(), itask.flow_nums)
