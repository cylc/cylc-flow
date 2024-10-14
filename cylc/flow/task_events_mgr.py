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
"""Task events manager.

This module provides logic to:
* Manage task messages (internal, polled or received).
* Set up retries on job failures (submission or execution).
* Generate task event handlers.
  * Retrieval of log files for completed remote jobs.
  * Email notification.
  * Custom event handlers.
* Manage invoking and retrying of task event handlers.
"""

from contextlib import suppress
from enum import Enum
from logging import DEBUG, INFO, getLevelName
import os
from shlex import quote
import shlex
from time import time
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Union,
    cast,
)

from cylc.flow import LOG, LOG_LEVELS
from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.exceptions import NoHostsError, PlatformLookupError
from cylc.flow.hostuserutil import get_host, get_user, is_remote_platform
from cylc.flow.parsec.config import ItemNotFoundError
from cylc.flow.pathutil import (
    get_remote_workflow_run_job_dir,
    get_workflow_run_job_dir)
from cylc.flow.subprocctx import SubFuncContext, SubProcContext
from cylc.flow.task_action_timer import (
    TaskActionTimer,
    TimerFlags
)
from cylc.flow.platforms import (
    get_platform, get_host_from_platform,
    log_platform_event
)
from cylc.flow.task_job_logs import (
    get_task_job_log,
    get_task_job_activity_log,
    JOB_LOG_OUT,
    JOB_LOG_ERR,
)
from cylc.flow.task_message import (
    ABORT_MESSAGE_PREFIX, FAIL_MESSAGE_PREFIX, VACATION_MESSAGE_PREFIX)
from cylc.flow.task_state import (
    TASK_STATUSES_ACTIVE,
    TASK_STATUS_PREPARING,
    TASK_STATUS_SUBMITTED,
    TASK_STATUS_SUBMIT_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_FAILED,
    TASK_STATUS_EXPIRED,
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING
)
from cylc.flow.task_outputs import (
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_SUBMIT_FAILED
)
from cylc.flow.wallclock import (
    get_current_time_string,
    get_seconds_as_interval_string as intvl_as_str
)
from cylc.flow.workflow_events import (
    EventData as WorkflowEventData,
    construct_mail_cmd,
    get_template_variables as get_workflow_template_variables,
    process_mail_footer,
)
from cylc.flow.workflow_status import RunMode


if TYPE_CHECKING:
    from cylc.flow.id import Tokens
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.scheduler import Scheduler


class CustomTaskEventHandlerContext(NamedTuple):
    key: Union[str, Sequence[str]]
    cmd: str


class TaskEventMailContext(NamedTuple):
    key: str
    mail_from: str
    mail_to: str


class TaskJobLogsRetrieveContext(NamedTuple):
    key: Union[str, Sequence[str]]
    platform_name: Optional[str]
    max_size: Optional[int]


class EventKey(NamedTuple):
    """Unique identifier for a task event.

    This contains event context information for event handlers.
    """

    """The event handler name."""
    handler: str

    """The task event."""
    event: str

    """The task event message.

    Warning: This information is not currently preserved in the DB so will be
    lost on restart.
    """
    message: str

    """The job tokens."""
    tokens: 'Tokens'


def get_event_id(event: str, itask: 'TaskProxy') -> str:
    """Return a unique event identifier.

    Some events are not unique e.g. task "started" is unique in that it can
    only happen once per-job, "warning", however, is not unique as this is a
    message severity level which could be associated with any number of
    custom task messages.

    To handle this tasks track non-unique-events and number them to ensure
    their EventKey's remain unique for ease of event tracking.

    Examples:
        >>> from types import SimpleNamespace

        # regular events are passed straight through:
        >>> get_event_id('whatever', SimpleNamespace())
        'whatever'

        # non-unique events get an integer added to the end:
        >>> get_event_id('warning', SimpleNamespace(non_unique_events={
        ...     'warning': None,
        ... }))
        'warning-1'
        >>> get_event_id('warning', SimpleNamespace(non_unique_events={
        ...     'warning': 2,
        ... }))
        'warning-2'

    """
    if event in TaskEventsManager.NON_UNIQUE_EVENTS:
        event = f'{event}-{itask.non_unique_events[event] or 1:d}'
    return event


def log_task_job_activity(ctx, workflow, point, name, submit_num=None):
    """Log an activity for a task job."""
    ctx_str = str(ctx)
    if not ctx_str:
        return
    if isinstance(ctx.cmd_key, tuple):  # An event handler
        submit_num = ctx.cmd_key[-1]
    job_activity_log = get_task_job_activity_log(
        workflow, point, name, submit_num)
    try:
        with open(os.path.expandvars(job_activity_log), "ab") as handle:
            handle.write((ctx_str + '\n').encode())
    except IOError:
        # This happens when there is no job directory. E.g., if a job host
        # selection command causes a submission failure, or if a waiting task
        # expires before a job log directory is otherwise needed.
        # (Don't log the exception content, it looks like a bug).
        LOG.info(ctx_str)
    if ctx.cmd and ctx.ret_code:
        LOG.error(ctx_str)


class EventData(Enum):
    """The following variables are available to task event handlers.

    They can be templated into event handlers with Python percent style string
    formatting e.g:

    .. code-block:: none

       %(workflow)s is running on %(host)s

    The ``%(event)s`` string, for instance, will be replaced by the actual
    event name when the handler is invoked.

    If no templates or arguments are specified the following default command
    line will be used:

    .. code-block:: none

       <event-handler> %(event)s %(workflow)s %(id)s %(message)s

    .. note::

       Substitution patterns should not be quoted in the template strings.
       This is done automatically where required.

    For an explanation of the substitution syntax, see
    `String Formatting Operations in the Python documentation
    <https://docs.python.org/3/library/stdtypes.html
    #printf-style-string-formatting>`_.

    """

    Event = 'event'
    """Event name."""

    Workflow = 'workflow'
    """Workflow ID."""

    Suite = 'suite'  # deprecated
    """Workflow ID.

    .. deprecated:: 8.0.0

       Use "workflow".
    """

    UUID = 'uuid'
    """The unique identification string for this workflow run.

    This string is preserved for the lifetime of the scheduler and is restored
    from the database on restart.
    """

    SuiteUUID = 'suite_uuid'  # deprecated
    """The unique identification string for this workflow run.

    .. deprecated:: 8.0.0

       Use 'uuid'.
    """

    CyclePoint = 'point'
    """The task's cycle point."""

    SubmitNum = 'submit_num'
    """The job's submit number.

    This starts at 1 and increments with each additional job submission.
    """

    TryNum = 'try_num'
    """The job's try number.

    The number of execution attempts.
    It starts at 1 and increments with automatic
    :cylc:conf:`flow.cylc[runtime][<namespace>]execution retry delays`.
    """

    ID = 'id'
    """The task ID (i.e. ``%(point)/%(name)``)."""

    Message = 'message'
    """Events message, if any."""

    JobRunnerName = 'job_runner_name'
    """The job runner name."""

    JobRunnerName_old = 'batch_sys_name'  # deprecated
    """The job runner name.

    .. deprecated:: 8.0.0

       Use "job_runner_name".
    """

    JobID = 'job_id'
    """The job ID in the job runner.

    I.E. The job submission ID. For background jobs this is the process ID.
    """

    JobID_old = 'batch_sys_job_id'  # deprecated
    """The job ID in the job runner.

    .. deprecated:: 8.0.0

       Use "job_id".
    """

    SubmitTime = 'submit_time'
    """Date-time when the job was submitted, in ISO8601 format."""

    StartTime = 'start_time'
    """Date-time when the job started, in ISO8601 format."""

    FinishTime = 'finish_time'
    """Date-time when the job finished, in ISO8601 format."""

    PlatformName = 'platform_name'
    """The name of the platform where the job is submitted."""

    UserAtHost = 'user@host'
    """The name of the platform where the job is submitted.

    .. deprecated:: 8.0.0

       Use "platform_name".

    .. versionchanged:: 8.0.0

       This now provides the platform name rather than ``user@host``.
    """

    TaskName = 'name'
    """The name of the task."""

    TaskURL = 'task_url'  # deprecated
    """The URL defined in the task's metadata.

    .. deprecated:: 8.0.0

       Use ``URL`` from ``<task metadata>``.
    """

    WorkflowURL = 'workflow_url'  # deprecated
    """The URL defined in the workflow's metadata.

    .. deprecated:: 8.0.0

       Use ``workflow_URL`` from ``workflow_<workflow metadata>``.
    """

    # NOTE: placeholder for task metadata (here for documentation reasons)
    TaskMeta = '<task metadata>'
    """Any task metadata defined in
    :cylc:conf:`flow.cylc[runtime][<namespace>][meta]` can be used e.g:

    ``%(title)s``
       Task title
    ``%(URL)s``
       Task URL
    ``%(importance)s``
       Example custom task metadata
    """

    # NOTE: placeholder for workflow metadata (here for documentation reasons)
    WorkflowMeta = 'workflow_<workflow metadata>'
    """Any workflow metadata defined in
    :cylc:conf:`flow.cylc[meta]` can be used with the ``workflow_``
    e.g. prefix:

    ``%(workflow_title)s``
       Workflow title
    ``%(workflow_URL)s``
       Workflow URL.
    ``%(workflow_rating)s``
       Example custom workflow metadata.
    """


def get_event_handler_data(task_cfg, workflow_cfg):
    """Extract event handler data from workflow and task metadata."""
    handler_data = {}
    # task metadata
    for key, value in task_cfg['meta'].items():
        if key == "URL":
            handler_data[EventData.TaskURL.value] = quote(value)
        handler_data[key] = quote(value)
    # workflow metadata
    for key, value in workflow_cfg['meta'].items():
        if key == "URL":
            handler_data[EventData.WorkflowURL.value] = quote(value)
        handler_data["workflow_" + key] = quote(value)
    return handler_data


class TaskEventsManager():
    """Task events manager.

    This class does the following:
    * Manage task messages (received or otherwise).
    * Set up task (submission) retries on job (submission) failures.
    * Generate and manage task event handlers.
    """
    EVENT_FAILED = TASK_OUTPUT_FAILED
    EVENT_LATE = "late"
    EVENT_RETRY = "retry"
    EVENT_STARTED = TASK_OUTPUT_STARTED
    EVENT_SUBMITTED = TASK_OUTPUT_SUBMITTED
    EVENT_EXPIRED = TASK_OUTPUT_EXPIRED
    EVENT_SUBMIT_FAILED = "submission failed"
    EVENT_SUBMIT_RETRY = "submission retry"
    EVENT_SUCCEEDED = TASK_OUTPUT_SUCCEEDED
    HANDLER_CUSTOM = "event-handler"
    HANDLER_MAIL = "event-mail"
    JOB_FAILED = "job failed"
    HANDLER_JOB_LOGS_RETRIEVE = "job-logs-retrieve"
    FLAG_INTERNAL = "(internal)"
    FLAG_RECEIVED = "(received)"
    FLAG_RECEIVED_IGNORED = "(received-ignored)"
    FLAG_POLLED = "(polled)"
    FLAG_POLLED_IGNORED = "(polled-ignored)"
    KEY_EXECUTE_TIME_LIMIT = 'execution_time_limit'
    NON_UNIQUE_EVENTS = ('warning', 'critical', 'custom')
    JOB_SUBMIT_SUCCESS_FLAG = 0
    JOB_SUBMIT_FAIL_FLAG = 1
    JOB_LOGS_RETRIEVAL_EVENTS = {
        EVENT_FAILED,
        EVENT_RETRY,
        EVENT_SUCCEEDED
    }

    workflow_cfg: Dict[str, Any]
    uuid_str: str
    # To be set by the task pool:
    spawn_func: Callable[['TaskProxy', str], Any]

    mail_interval: float = 0
    mail_smtp: Optional[str] = None
    mail_footer: Optional[str] = None

    def __init__(
        self, workflow, proc_pool, workflow_db_mgr, broadcast_mgr,
        xtrigger_mgr, data_store_mgr, timestamp, bad_hosts,
        reset_inactivity_timer_func
    ):
        self.workflow = workflow
        self.proc_pool = proc_pool
        self.workflow_db_mgr = workflow_db_mgr
        self.broadcast_mgr = broadcast_mgr
        self.xtrigger_mgr = xtrigger_mgr
        self.data_store_mgr = data_store_mgr
        self.next_mail_time = None
        self.reset_inactivity_timer_func = reset_inactivity_timer_func
        # NOTE: do not mutate directly
        # use the {add,remove,unset_waiting}_event_timers methods
        self._event_timers: Dict[EventKey, Any] = {}
        # NOTE: flag for DB use
        self.event_timers_updated = True
        self.timestamp = timestamp
        self.bad_hosts = bad_hosts

    @staticmethod
    def check_poll_time(itask, now=None):
        """Set the next task execution/submission poll time.

        If now is set, set the timer only if the previous delay is done.
        Return the next delay.
        """
        if not itask.state(*TASK_STATUSES_ACTIVE):
            # Reset, task not active
            itask.timeout = None
            itask.poll_timer = None
            return None
        ctx = (itask.submit_num, itask.state.status)
        if itask.poll_timer is None or itask.poll_timer.ctx != ctx:
            # Reset, timer no longer relevant
            itask.timeout = None
            itask.poll_timer = None
            return None
        if now is not None and not itask.poll_timer.is_delay_done(now):
            return False
        if itask.poll_timer.num is None:
            itask.poll_timer.num = 0
        itask.poll_timer.next(no_exhaust=True)
        return True

    def check_job_time(self, itask, now):
        """Check/handle job timeout and poll timer"""
        can_poll = self.check_poll_time(itask, now)
        if itask.timeout is None or now <= itask.timeout:
            return can_poll
        # Timeout reached for task, emit event and reset itask.timeout
        if itask.state(TASK_STATUS_RUNNING):
            time_ref = itask.summary['started_time']
            event = 'execution timeout'
        elif itask.state(TASK_STATUS_SUBMITTED):
            time_ref = itask.summary['submitted_time']
            event = 'submission timeout'
        msg = event
        with suppress(TypeError, ValueError):
            msg += ' after %s' % intvl_as_str(itask.timeout - time_ref)
        itask.timeout = None  # emit event only once
        if msg and event:
            LOG.warning(f"[{itask}] {msg}")
            self.setup_event_handlers(itask, event, msg)
            return True
        else:
            return can_poll

    def _get_remote_conf(self, itask, key):
        """Get deprecated "[remote]" items that default to platforms."""
        overrides = self.broadcast_mgr.get_broadcast(itask.tokens)
        SKEY = 'remote'
        if SKEY not in overrides:
            overrides[SKEY] = {}
        return (
            overrides[SKEY].get(key) or
            itask.tdef.rtconfig[SKEY][key] or
            itask.platform[key]
        )

    def _get_workflow_platforms_conf(self, itask, key):
        """Return top level [runtime] items that default to platforms."""
        overrides = self.broadcast_mgr.get_broadcast(itask.tokens)
        return (
            overrides.get(key) or
            itask.tdef.rtconfig[key] or
            itask.platform[key]
        )

    def process_events(self, schd: 'Scheduler') -> None:
        """Process task events that were created by "setup_event_handlers".
        """
        ctx_groups: dict = {}
        now = time()
        for id_key, timer in self._event_timers.copy().items():
            if timer.is_waiting:
                continue
            # Set timer if timeout is None.
            if not timer.is_timeout_set():
                if timer.next() is None:
                    LOG.warning(
                        f"{id_key.tokens.relative_id}"
                        f" handler:{id_key.handler}"
                        f" for task event:{id_key.event} failed"
                    )
                    self.remove_event_timer(id_key)
                    continue
                # Report retries and delayed 1st try
                msg = None
                if timer.num > 1:
                    msg = (
                        f"handler:{id_key.handler}"
                        f" for task event:{id_key.event} failed,"
                        f" retrying in {timer.delay_timeout_as_str()}"
                    )
                elif timer.delay:
                    msg = (
                        f"handler:{id_key.handler}"
                        f" for task event:{id_key.event} will"
                        f" run after {timer.delay_timeout_as_str()}"
                    )
                if msg:
                    LOG.debug("%s %s", id_key.tokens.relative_id, msg)
            # Ready to run?
            if not timer.is_delay_done() or (
                # Avoid flooding user's mail box with mail notification.
                # Group together as many notifications as possible within a
                # given interval.
                isinstance(timer.ctx, TaskEventMailContext) and
                not schd.stop_mode and
                self.next_mail_time is not None and
                self.next_mail_time > now
            ):
                continue

            timer.set_waiting()
            if isinstance(timer.ctx, CustomTaskEventHandlerContext):
                # Run custom event handlers on their own
                self.proc_pool.put_command(
                    SubProcContext(
                        ((id_key.handler, id_key.event), id_key.tokens['job']),
                        timer.ctx.cmd,
                        env=os.environ,
                        shell=True,  # nosec
                    ),  # designed to run user defined code
                    callback=self._custom_handler_callback,
                    callback_args=[schd, id_key]
                )
            else:
                # Group together built-in event handlers, where possible
                if timer.ctx not in ctx_groups:
                    ctx_groups[timer.ctx] = []
                ctx_groups[timer.ctx].append(id_key)

        next_mail_time = now + self.mail_interval
        for ctx, id_keys in ctx_groups.items():
            if isinstance(ctx, TaskEventMailContext):
                # Set next_mail_time if any mail sent
                self.next_mail_time = next_mail_time
                self._process_event_email(schd, ctx, id_keys)
            elif isinstance(ctx, TaskJobLogsRetrieveContext):
                self._process_job_logs_retrieval(schd, ctx, id_keys)

    def process_message(
        self,
        itask: 'TaskProxy',
        severity: Union[str, int],
        message: str,
        event_time: Optional[str] = None,
        flag: str = FLAG_INTERNAL,
        submit_num: Optional[int] = None,
        forced: bool = False
    ) -> Optional[bool]:
        """Parse a task message and update task state.

        Incoming, e.g. "succeeded at <TIME>", may be from task job or polling.

        It is possible for the current state of a task to be inconsistent with
        a message (whether internal, received or polled) e.g. due to a late
        poll result, or a network outage, or manual state reset. To handle
        this, if a message would take the task state backward, issue a poll to
        confirm instead of changing state - then always believe the next
        message. Note that the next message might not be the result of this
        confirmation poll, in the unlikely event that a job emits a succession
        of messages very quickly, but this is the best we can do without
        somehow uniquely associating each poll with its result message.

        Arguments:
            itask:
                The task proxy object relevant for the message.
            severity:
                Message severity, should be a recognised logging level.
            message:
                Message content.
            event_time:
                Event time stamp. Expect ISO8601 date time string.
                If not specified, use current time.
            flag:
                If specified, can be:
                    FLAG_INTERNAL (default):
                        To indicate an internal message.
                    FLAG_RECEIVED:
                        To indicate a message received from a job or an
                        external source.
                    FLAG_POLLED:
                        To indicate a message resulted from a poll.
            submit_num:
                The submit number of the task relevant for the message.
                If not specified, use latest submit number.
            forced:
                If this message is due to manual completion or not (cylc set)

        Return:
            None: in normal circumstances.
            True: if polling is required to confirm a reversal of status.

        """

        # Log messages
        if event_time is None:
            event_time = get_current_time_string()
        if submit_num is None:
            submit_num = itask.submit_num
        if isinstance(severity, int):
            severity = cast('str', getLevelName(severity))
        lseverity = str(severity).lower()

        # Any message represents activity.
        self.reset_inactivity_timer_func()

        if not self._process_message_check(
            itask, severity, message, event_time, flag, submit_num, forced
        ):
            return None

        # always update the workflow state summary for latest message
        if flag == self.FLAG_POLLED:
            new_msg = f'{message} {self.FLAG_POLLED}'
        else:
            new_msg = message
        self.data_store_mgr.delta_job_msg(
            itask.tokens.duplicate(job=str(submit_num)),
            new_msg
        )

        # Satisfy my output, if possible, and spawn children.
        # (first remove signal: failed/EXIT -> failed)

        # Complete the corresponding task output, if there is one.
        msg0 = message.split('/')[0]
        if message.startswith(ABORT_MESSAGE_PREFIX):
            msg0 = TASK_OUTPUT_FAILED

        completed_output: Optional[bool] = False
        if msg0 not in [TASK_OUTPUT_SUBMIT_FAILED, TASK_OUTPUT_FAILED]:
            completed_output = (
                itask.state.outputs.set_message_complete(msg0, forced)
            )
            if completed_output:
                self.data_store_mgr.delta_task_output(itask, msg0)

        for implied in (
            itask.state.outputs.get_incomplete_implied(msg0)
        ):
            # Set submitted and/or started first, if skipped.
            # (whether by forced set, or missed message).
            LOG.info(f"[{itask}] setting implied output: {implied}")
            self.process_message(
                itask, INFO, implied, event_time,
                self.FLAG_INTERNAL, submit_num, forced
            )

        if message == self.EVENT_STARTED:
            if (
                flag == self.FLAG_RECEIVED
                and itask.state.is_gt(TASK_STATUS_RUNNING)
            ):
                # Already running.
                return True
            self._process_message_started(itask, event_time, forced)
            self.spawn_children(itask, TASK_OUTPUT_STARTED)

        elif message == self.EVENT_SUCCEEDED:
            self._process_message_succeeded(itask, event_time, forced)
            self.spawn_children(itask, TASK_OUTPUT_SUCCEEDED)

        elif message == self.EVENT_EXPIRED:
            self._process_message_expired(itask, event_time, forced)
            self.spawn_children(itask, TASK_OUTPUT_EXPIRED)

        elif message == self.EVENT_FAILED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)
            ):
                # Already failed.
                return True
            if self._process_message_failed(
                itask, event_time, self.JOB_FAILED, forced
            ):
                self.spawn_children(itask, TASK_OUTPUT_FAILED)

        elif message == self.EVENT_SUBMIT_FAILED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_SUBMIT_FAILED)
            ):
                # Already submit-failed
                return True
            if self._process_message_submit_failed(
                itask, event_time, submit_num, forced
            ):
                self.spawn_children(itask, TASK_OUTPUT_SUBMIT_FAILED)

        elif message == self.EVENT_SUBMITTED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gte(TASK_STATUS_SUBMITTED)
            ):
                # Already submitted.
                return True
            self._process_message_submitted(itask, event_time, forced)
            self.spawn_children(itask, TASK_OUTPUT_SUBMITTED)

            # ... but either way update the job ID in the job proxy (it only
            # comes in via the submission message).
            if itask.tdef.run_mode != RunMode.SIMULATION:
                job_tokens = itask.tokens.duplicate(
                    job=str(itask.submit_num)
                )
                self.data_store_mgr.delta_job_attr(
                    job_tokens, 'job_id', itask.summary['submit_method_id'])
            else:
                # In simulation mode submitted implies started:
                self.spawn_children(itask, TASK_OUTPUT_STARTED)

        elif message.startswith(FAIL_MESSAGE_PREFIX):
            # Task received signal.
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)
            ):
                # Already failed.
                return True
            signal = message[len(FAIL_MESSAGE_PREFIX):]
            self._db_events_insert(itask, "signaled", signal)
            self.workflow_db_mgr.put_update_task_jobs(
                itask, {"run_signal": signal})
            if self._process_message_failed(
                itask, event_time, self.JOB_FAILED, forced
            ):
                self.spawn_children(itask, TASK_OUTPUT_FAILED)

        elif message.startswith(ABORT_MESSAGE_PREFIX):
            # Task aborted with message
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)
            ):
                # Already failed.
                return True
            aborted_with = message[len(ABORT_MESSAGE_PREFIX):]
            self._db_events_insert(itask, "aborted", message)
            self.workflow_db_mgr.put_update_task_jobs(
                itask, {"run_signal": aborted_with})
            if self._process_message_failed(
                itask, event_time, aborted_with, forced
            ):
                self.spawn_children(itask, TASK_OUTPUT_FAILED)

        elif message.startswith(VACATION_MESSAGE_PREFIX):
            # Task job pre-empted into a vacation state
            self._db_events_insert(itask, "vacated", message)
            itask.set_summary_time('started')  # unset
            if TimerFlags.SUBMISSION_RETRY in itask.try_timers:
                itask.try_timers[TimerFlags.SUBMISSION_RETRY].num = 0
            itask.job_vacated = True
            # Believe this and change state without polling (could poll?).
            if itask.state_reset(TASK_STATUS_SUBMITTED, forced=forced):
                itask.state_reset(is_queued=False, forced=forced)
                self.data_store_mgr.delta_task_state(itask)
                self.data_store_mgr.delta_task_queued(itask)
            self._reset_job_timers(itask)
            # We should really have a special 'vacated' handler, but given that
            # this feature can only be used on the deprecated loadleveler
            # system, we should probably aim to remove support for job vacation
            # instead. Otherwise, we should have:
            # self.setup_event_handlers(itask, 'vacated', message)

        elif completed_output:
            # Message of a custom task output.
            # No state change.
            # Log completion of o      (not needed for standard outputs)
            trigger = itask.state.outputs.get_trigger(message)
            LOG.info(f"[{itask}] completed output {trigger}")
            self.setup_event_handlers(itask, trigger, message)
            self.spawn_children(itask, msg0)

        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            # No state change.
            LOG.debug(f"[{itask}] unhandled: {message}")
            self._db_events_insert(
                itask, (f"message {lseverity}"), message)

        if lseverity in self.NON_UNIQUE_EVENTS:
            itask.non_unique_events.update({lseverity: 1})
            self.setup_event_handlers(itask, lseverity, message)

        return None

    def _process_message_check(
        self,
        itask: 'TaskProxy',
        severity: str,
        message: str,
        event_time: str,
        flag: str,
        submit_num: int,
        forced: bool = False
    ) -> bool:
        """Helper for `.process_message`.

        See `.process_message` for argument list
        Check whether to process/skip message.
        Return True if `.process_message` should continue, False otherwise.
        """
        if itask.transient or forced:
            return True

        if self.timestamp:
            timestamp = f" at {event_time}"
        else:
            timestamp = ""
        if flag == self.FLAG_RECEIVED and submit_num != itask.submit_num:
            # Ignore received messages from old jobs
            LOG.warning(
                f"[{itask}] "
                f"{self.FLAG_RECEIVED_IGNORED}{message}{timestamp} "
                f"for job({submit_num:02d}) != job({itask.submit_num:02d})"
            )
            return False

        if (
            itask.state(TASK_STATUS_WAITING)
            # Polling in live mode only:
            and itask.tdef.run_mode == RunMode.LIVE
            and (
                (
                    # task has a submit-retry lined up
                    TimerFlags.SUBMISSION_RETRY in itask.try_timers
                    and itask.try_timers[
                        TimerFlags.SUBMISSION_RETRY].num > 0
                )
                or
                (
                    # task has an execution-retry lined up
                    TimerFlags.EXECUTION_RETRY in itask.try_timers
                    and itask.try_timers[
                        TimerFlags.EXECUTION_RETRY].num > 0
                )
            )
        ):
            # Ignore messages if task has a retry lined up
            # (caused by polling overlapping with task failure)
            if flag == self.FLAG_RECEIVED:
                LOG.warning(
                    f"[{itask}] "
                    f"{self.FLAG_RECEIVED_IGNORED}{message}{timestamp}"
                )

            else:
                LOG.warning(
                    f"[{itask}] "
                    f"{self.FLAG_POLLED_IGNORED}{message}{timestamp}"
                )
            return False

        severity_lvl: int = LOG_LEVELS.get(severity, INFO)
        # Demote log level to DEBUG if this duplicates task state change
        # logging (and not manual poll). Failed messages are not demoted
        # however - they are more important and have no obvious corresponding
        # state change when there are retries lined up).
        if severity_lvl > DEBUG and flag != self.FLAG_POLLED and message in {
            self.EVENT_SUBMITTED, self.EVENT_STARTED, self.EVENT_SUCCEEDED,
        }:
            severity_lvl = DEBUG
        LOG.log(severity_lvl, f"[{itask}] {flag}{message}{timestamp}")
        return True

    def setup_event_handlers(self, itask, event, message):
        """Set up handlers for a task event."""
        if itask.tdef.run_mode != RunMode.LIVE:
            return
        msg = ""
        if message != f"job {event}":
            msg = message
        self._db_events_insert(itask, event, msg)
        self._setup_job_logs_retrieval(itask, event)
        self._setup_event_mail(itask, event, message)
        self._setup_custom_event_handlers(itask, event, message)

    def _custom_handler_callback(
        self,
        ctx,
        schd: 'Scheduler',
        id_key: EventKey,
    ) -> None:
        """Callback when a custom event handler is done."""
        tokens = id_key.tokens
        log_task_job_activity(
            ctx,
            schd.workflow,
            tokens['cycle'],
            tokens['task'],
            tokens['job'],
        )
        if ctx.ret_code == 0:
            self.remove_event_timer(id_key)
        else:
            self.unset_waiting_event_timer(id_key)

    def _db_events_insert(self, itask, event="", message=""):
        """Record an event to the DB."""
        self.workflow_db_mgr.put_insert_task_events(itask, {
            "time": get_current_time_string(),
            "event": event,
            "message": message})

    def _process_event_email(
        self,
        schd: 'Scheduler',
        ctx: TaskEventMailContext,
        id_keys: List[EventKey],
    ) -> None:
        """Process event notification, by email."""
        if len(id_keys) == 1:
            id_key = id_keys[0]
            subject = (
                f'[{id_key.tokens.relative_id} {id_key.event}]'
                f' {schd.workflow}'
            )
        else:
            event_set = {id_key.event for id_key in id_keys}
            if len(event_set) == 1:
                # 1 event from n tasks
                subject = "[%d tasks %s] %s" % (
                    len(id_keys), event_set.pop(), schd.workflow)
            else:
                # n events from n tasks
                subject = "[%d task events] %s" % (
                    len(id_keys), schd.workflow)

        # STDIN for mail, tasks
        stdin_str = ""
        for id_key in sorted(id_keys):
            stdin_str += f'job: {id_key.tokens.relative_id}\n'
            stdin_str += f'event: {id_key.event}\n'
            stdin_str += f'message: {id_key.message}\n\n'

        # STDIN for mail, event info + workflow detail
        stdin_str += "\n"
        for key, value in (
            (WorkflowEventData.Workflow.value, schd.workflow),
            (WorkflowEventData.Host.value, schd.host),
            (WorkflowEventData.Port.value, schd.server.port),
            (WorkflowEventData.Owner.value, schd.owner),
        ):
            stdin_str += '%s: %s\n' % (key, value)

        if self.mail_footer:
            stdin_str += process_mail_footer(
                self.mail_footer,
                get_workflow_template_variables(
                    schd,
                    id_keys[-1].event,
                    id_keys[-1].message,
                ),
            )
        self._send_mail(ctx, subject, stdin_str, id_keys, schd)

    def _send_mail(
        self,
        ctx: TaskEventMailContext,
        subject: str,
        stdin_str: str,
        id_keys: List[EventKey],
        schd: 'Scheduler',
    ) -> None:
        cmd = construct_mail_cmd(
            subject, from_address=ctx.mail_from, to_address=ctx.mail_to
        )
        # SMTP server
        env = dict(os.environ)
        if self.mail_smtp:
            env["smtp"] = self.mail_smtp
        self.proc_pool.put_command(
            SubProcContext(
                ctx, cmd, env=env, stdin_str=stdin_str, id_keys=id_keys,
            ),
            callback=self._event_email_callback, callback_args=[schd])

    def _event_email_callback(self, proc_ctx, schd) -> None:
        """Call back when email notification command exits."""
        id_key: EventKey
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            try:
                if proc_ctx.ret_code == 0:
                    self.remove_event_timer(id_key)
                    log_ctx = SubProcContext(
                        (
                            (id_key.handler, id_key.event),
                            id_key.tokens['job']
                        ),
                        None,
                    )
                    log_ctx.ret_code = 0
                    log_task_job_activity(
                        log_ctx,
                        schd.workflow,
                        id_key.tokens['cycle'],
                        id_key.tokens['task'],
                        id_key.tokens['job'],
                    )
                else:
                    self.unset_waiting_event_timer(id_key)
            except KeyError as exc:
                LOG.exception(exc)

    def _get_events_conf(
        self, itask: 'TaskProxy', key: str, default: Any = None
    ) -> Any:
        """Return an events setting from workflow then global configuration."""
        for getter in (
            self.broadcast_mgr.get_broadcast(itask.tokens).get("events"),
            itask.tdef.rtconfig["mail"],
            itask.tdef.rtconfig["events"],
            self.workflow_cfg.get("scheduler", {}).get("mail", {}),
            glbl_cfg().get(["scheduler", "mail"]),
            glbl_cfg().get()["task events"],
        ):
            try:
                value = getter.get(key)
            except (AttributeError, ItemNotFoundError, KeyError):
                pass
            else:
                if value is not None:
                    return value
        return default

    def _process_job_logs_retrieval(
        self,
        schd: 'Scheduler',
        ctx: TaskJobLogsRetrieveContext,
        id_keys: List[EventKey],
    ) -> None:
        """Process retrieval of task job logs from remote user@host."""
        # get a host to run retrieval on
        try:
            platform = get_platform(ctx.platform_name)
            host = get_host_from_platform(platform, bad_hosts=self.bad_hosts)
        except NoHostsError:
            # All of the platforms hosts have been found to be uncontactable.
            # Reset the bad hosts to allow retrieval retry to take place.
            self.bad_hosts -= set(platform['hosts'])
            try:
                # Get a new host and try again.
                host = get_host_from_platform(
                    platform,
                    bad_hosts=self.bad_hosts
                )
            except NoHostsError:
                # We really can't get a host to try on e.g. no hosts
                # configured (shouldn't happen). Nothing more we can do here,
                # move onto the next submission retry.
                for id_key in id_keys:
                    self.unset_waiting_event_timer(id_key)
                return
        except PlatformLookupError:
            log_platform_event(
                'Unable to retrieve job logs.',
                {'name': ctx.platform_name},
                level='warning',
            )
            return

        # construct the retrieval command
        ssh_str = str(platform["ssh command"])
        rsync_str = str(platform["retrieve job logs command"])
        cmd = shlex.split(rsync_str) + ["--rsh=" + ssh_str]
        if LOG.isEnabledFor(DEBUG):
            cmd.append("-v")
        if ctx.max_size:
            cmd.append("--max-size=%s" % (ctx.max_size,))
        # Includes and excludes
        includes = set()
        for id_key in id_keys:
            # Include relevant directories, all levels needed
            includes.add("/%s" % (id_key.tokens['cycle']))
            includes.add(
                "/%s/%s" % (
                    id_key.tokens['cycle'],
                    id_key.tokens['task']
                )
            )
            includes.add(
                "/%s/%s/%02d" % (
                    id_key.tokens['cycle'],
                    id_key.tokens['task'],
                    id_key.tokens['job'],
                )
            )
            includes.add(
                "/%s/%s/%02d/**" % (
                    id_key.tokens['cycle'],
                    id_key.tokens['task'],
                    id_key.tokens['job'],
                )
            )
        cmd += ["--include=%s" % (include) for include in sorted(includes)]
        cmd.append("--exclude=/**")  # exclude everything else
        # Remote source
        cmd.append("%s:%s/" % (
            host,
            get_remote_workflow_run_job_dir(
                schd.workflow).replace('$HOME/', ''))
        )
        # Local target
        cmd.append(get_workflow_run_job_dir(schd.workflow) + "/")

        # schedule command
        self.proc_pool.put_command(
            SubProcContext(
                ctx, cmd, env=dict(os.environ), id_keys=id_keys, host=host
            ),
            bad_hosts=self.bad_hosts,
            callback=self._job_logs_retrieval_callback,
            callback_args=[schd],
            callback_255=self._job_logs_retrieval_callback_255
        )

    def _job_logs_retrieval_callback_255(self, proc_ctx, schd) -> None:
        """Call back when log job retrieval fails with a 255 error."""
        self.bad_hosts.add(proc_ctx.host)
        for _ in proc_ctx.cmd_kwargs["id_keys"]:
            for key in proc_ctx.cmd_kwargs['id_keys']:
                timer = self._event_timers[key]
                timer.reset()

    def _job_logs_retrieval_callback(self, proc_ctx, schd) -> None:
        """Call back when log job retrieval completes."""
        if (
            (proc_ctx.ret_code and LOG.isEnabledFor(DEBUG))
            or (proc_ctx.ret_code and proc_ctx.ret_code != 255)
        ):
            LOG.error(proc_ctx)
        else:
            LOG.debug(proc_ctx)
        id_key: EventKey
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            try:
                # All completed jobs are expected to have a "job.out".
                fnames = [JOB_LOG_OUT]
                with suppress(TypeError):
                    if id_key.event not in 'succeeded':
                        fnames.append(JOB_LOG_ERR)
                fname_oks = {}
                for fname in fnames:
                    fname_oks[fname] = os.path.exists(get_task_job_log(
                        schd.workflow,
                        id_key.tokens['cycle'],
                        id_key.tokens['task'],
                        id_key.tokens['job'],
                        fname,
                    ))
                # All expected paths must exist to record a good attempt
                log_ctx = SubProcContext(
                    (
                        (id_key.handler, id_key.event),
                        id_key.tokens['job']
                    ),
                    None,
                )
                if all(fname_oks.values()):
                    log_ctx.ret_code = 0
                    self.remove_event_timer(id_key)
                else:
                    log_ctx.ret_code = 1
                    log_ctx.err = "File(s) not retrieved:"
                    for fname, exist_ok in sorted(fname_oks.items()):
                        if not exist_ok:
                            log_ctx.err += " %s" % fname
                    self.unset_waiting_event_timer(id_key)
                log_task_job_activity(
                    log_ctx,
                    schd.workflow,
                    id_key.tokens['cycle'],
                    id_key.tokens['task'],
                    id_key.tokens['job'],
                )
            except KeyError as exc:
                LOG.exception(exc)

    def _retry_task(self, itask, wallclock_time, submit_retry=False):
        """Retry a task.

        Args:
            itask (cylc.flow.task_proxy.TaskProxy):
                The task to retry.
            wallclock_time (float):
                Unix time to schedule the retry for.
            submit_retry (bool):
                False if this is an execution retry.
                True if this is a submission retry.

        """
        # derive an xtrigger label for this retry
        label = '_'.join((
            '_cylc',
            'submit_retry' if submit_retry else 'retry',
            itask.identity
        ))
        kwargs = {
            'trigger_time': wallclock_time
        }

        # if this isn't the first retry the xtrigger will already exist
        if label in itask.state.xtriggers:
            # retry xtrigger already exists from a previous retry, modify it
            self.xtrigger_mgr.mutate_trig(label, kwargs)
            itask.state.xtriggers[label] = False
        else:
            # create a new retry xtrigger
            xtrig = SubFuncContext(
                label,
                'wall_clock',
                [],
                kwargs
            )
            self.xtrigger_mgr.xtriggers.add_trig(
                label,
                xtrig,
                os.getenv("CYLC_WORKFLOW_RUN_DIR")
            )
            itask.state.add_xtrigger(label)

        if itask.state_reset(TASK_STATUS_WAITING):
            self.data_store_mgr.delta_task_state(itask)

    def _process_message_failed(self, itask, event_time, message, forced):
        """Helper for process_message, handle a failed message.

        Return True if no retries (hence go to the failed state).
        """
        no_retries = False
        if event_time is None:
            event_time = get_current_time_string()
        itask.set_summary_time('finished', event_time)
        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self.data_store_mgr.delta_job_time(job_tokens, 'finished', event_time)
        self.data_store_mgr.delta_job_state(job_tokens, TASK_STATUS_FAILED)
        self.workflow_db_mgr.put_update_task_jobs(itask, {
            "run_status": 1,
            "time_run_exit": event_time,
        })
        if (
                forced
                or TimerFlags.EXECUTION_RETRY not in itask.try_timers
                or itask.try_timers[TimerFlags.EXECUTION_RETRY].next() is None
        ):
            # No retry lined up: definitive failure.
            no_retries = True
            if itask.state_reset(TASK_STATUS_FAILED, forced=forced):
                self.setup_event_handlers(itask, self.EVENT_FAILED, message)
                self.data_store_mgr.delta_task_state(itask)
                itask.state.outputs.set_message_complete(TASK_OUTPUT_FAILED)
                self.data_store_mgr.delta_task_output(
                    itask, TASK_OUTPUT_FAILED)
                self.data_store_mgr.delta_task_state(itask)
        else:
            # There is an execution retry lined up.
            timer = itask.try_timers[TimerFlags.EXECUTION_RETRY]
            self._retry_task(itask, timer.timeout)
            delay_msg = f"retrying in {timer.delay_timeout_as_str()}"
            LOG.warning(f"[{itask}] {delay_msg}")
            msg = f"{self.JOB_FAILED}, {delay_msg}"
            self.setup_event_handlers(itask, self.EVENT_RETRY, msg)
        self._reset_job_timers(itask)
        return no_retries

    def _process_message_started(self, itask, event_time, forced):
        """Helper for process_message, handle a started message."""
        if itask.job_vacated:
            itask.job_vacated = False
            LOG.warning(f"[{itask}] Vacated job restarted")
        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self.data_store_mgr.delta_job_time(job_tokens, 'started', event_time)
        self.data_store_mgr.delta_job_state(job_tokens, TASK_STATUS_RUNNING)
        itask.set_summary_time('started', event_time)
        self.workflow_db_mgr.put_update_task_jobs(itask, {
            "time_run": itask.summary['started_time_string']})
        if itask.state_reset(TASK_STATUS_RUNNING, forced=forced):
            self.setup_event_handlers(
                itask, self.EVENT_STARTED, f'job {self.EVENT_STARTED}')
            self.data_store_mgr.delta_task_state(itask)
        self._reset_job_timers(itask)

        # submission was successful so reset submission try number
        if TimerFlags.SUBMISSION_RETRY in itask.try_timers:
            itask.try_timers[TimerFlags.SUBMISSION_RETRY].num = 0

    def _process_message_expired(self, itask, event_time, forced):
        """Helper for process_message, handle task expiry."""
        if not itask.state_reset(TASK_STATUS_EXPIRED, forced=forced):
            return
        self.data_store_mgr.delta_task_state(itask)
        self.data_store_mgr.delta_task_queued(itask)
        self.setup_event_handlers(
            itask,
            self.EVENT_EXPIRED,
            "Task expired: will not submit job."
        )

    def _process_message_succeeded(self, itask, event_time, forced):
        """Helper for process_message, handle a succeeded message.

        Ignore forced.
        """

        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self.data_store_mgr.delta_job_time(job_tokens, 'finished', event_time)
        self.data_store_mgr.delta_job_state(job_tokens, TASK_STATUS_SUCCEEDED)
        itask.set_summary_time('finished', event_time)
        self.workflow_db_mgr.put_update_task_jobs(itask, {
            "run_status": 0,
            "time_run_exit": event_time,
        })
        # Update mean elapsed time only on task succeeded.
        if itask.summary['started_time'] is not None:
            itask.tdef.elapsed_times.append(
                itask.summary['finished_time'] -
                itask.summary['started_time'])
        if itask.state_reset(TASK_STATUS_SUCCEEDED, forced=forced):
            self.setup_event_handlers(
                itask, self.EVENT_SUCCEEDED, f"job {self.EVENT_SUCCEEDED}")
            self.data_store_mgr.delta_task_state(itask)
        self._reset_job_timers(itask)

    def _process_message_submit_failed(
        self, itask, event_time, submit_num, forced
    ):
        """Helper for process_message, handle a submit-failed message.

        Return True if no retries (hence go to the submit-failed state).
        """
        no_retries = False
        LOG.critical(f"[{itask}] {self.EVENT_SUBMIT_FAILED}")
        if event_time is None:
            event_time = get_current_time_string()
        self.workflow_db_mgr.put_update_task_jobs(itask, {
            "time_submit_exit": event_time,
            "submit_status": 1,
        })
        itask.summary['submit_method_id'] = None
        if (
                forced
                or TimerFlags.SUBMISSION_RETRY not in itask.try_timers
                or itask.try_timers[TimerFlags.SUBMISSION_RETRY].next() is None
        ):
            # No submission retry lined up: definitive failure.
            # See github #476.
            no_retries = True
            if itask.state_reset(TASK_STATUS_SUBMIT_FAILED, forced=forced):
                self.setup_event_handlers(
                    itask, self.EVENT_SUBMIT_FAILED,
                    f'job {self.EVENT_SUBMIT_FAILED}')
                itask.state.outputs.set_message_complete(
                    TASK_OUTPUT_SUBMIT_FAILED
                )
                self.data_store_mgr.delta_task_output(
                    itask, TASK_OUTPUT_SUBMIT_FAILED)
                self.data_store_mgr.delta_task_state(itask)
        else:
            # There is a submission retry lined up.
            timer = itask.try_timers[TimerFlags.SUBMISSION_RETRY]
            self._retry_task(itask, timer.timeout, submit_retry=True)
            delay_msg = f"retrying in {timer.delay_timeout_as_str()}"
            LOG.warning(f"[{itask}] {delay_msg}")
            msg = f"job {self.EVENT_SUBMIT_FAILED}, {delay_msg}"
            self.setup_event_handlers(itask, self.EVENT_SUBMIT_RETRY, msg)

        # Register newly submit-failed job with the database and datastore.
        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self._insert_task_job(
            itask, event_time, self.JOB_SUBMIT_FAIL_FLAG, forced=forced)
        self.data_store_mgr.delta_job_state(
            job_tokens,
            TASK_STATUS_SUBMIT_FAILED
        )
        self._reset_job_timers(itask)

        return no_retries

    def _process_message_submitted(
        self, itask: 'TaskProxy', event_time: str, forced: bool
    ) -> None:
        """Helper for process_message, handle a submit-succeeded message."""
        with suppress(KeyError):
            summary = itask.summary
            LOG.info(
                f"[{itask}] submitted to "
                f"{summary['platforms_used'][itask.submit_num]}:"
                f"{summary['job_runner_name']}"
                f"[{summary['submit_method_id']}]"
            )

        itask.set_summary_time('submitted', event_time)
        if itask.tdef.run_mode == RunMode.SIMULATION:
            # Simulate job started as well.
            itask.set_summary_time('started', event_time)
            if itask.state_reset(TASK_STATUS_RUNNING, forced=forced):
                self.data_store_mgr.delta_task_state(itask)
            itask.state.outputs.set_message_complete(TASK_OUTPUT_STARTED)
            self.data_store_mgr.delta_task_output(itask, TASK_OUTPUT_STARTED)

        else:
            # Unset started and finished times in case of resubmission.
            itask.set_summary_time('started')
            itask.set_summary_time('finished')
            if itask.state.status == TASK_STATUS_PREPARING:
                # The job started message can (rarely) come in before the
                # submit command returns - in which case do not go back to
                # 'submitted'.
                if itask.state_reset(TASK_STATUS_SUBMITTED, forced=forced):
                    itask.state_reset(is_queued=False, forced=forced)
                    self.setup_event_handlers(
                        itask,
                        self.EVENT_SUBMITTED,
                        f'job {self.EVENT_SUBMITTED}',
                    )
                    self.data_store_mgr.delta_task_state(itask)
                    self.data_store_mgr.delta_task_queued(itask)
                self._reset_job_timers(itask)

        # Register the newly submitted job with the database and datastore.
        # Do after itask has changed state
        self._insert_task_job(
            itask, event_time, self.JOB_SUBMIT_SUCCESS_FLAG, forced=forced)
        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self.data_store_mgr.delta_job_time(
            job_tokens,
            'submitted',
            event_time,
        )
        if itask.tdef.run_mode == RunMode.SIMULATION:
            # Simulate job started as well.
            self.data_store_mgr.delta_job_time(
                job_tokens,
                'started',
                event_time,
            )
        else:
            self.data_store_mgr.delta_job_state(
                job_tokens,
                TASK_STATUS_SUBMITTED,
            )

    def _insert_task_job(
        self,
        itask: 'TaskProxy',
        event_time: str,
        submit_status: int,
        forced: bool = False
    ):
        """Insert a new job proxy into the datastore.

        Args:
            itask: create a job proxy for this task proxy
            event_time: time of job submission
            submit_status: 0 (success), 1 (fail)

        """
        # itask.jobs appends for automatic retries (which reuse the same task
        # proxy) but a retriggered task that was not already in the pool will
        # not see previous submissions (so can't use itask.jobs[submit_num-1]).
        # And transient tasks, used for setting outputs and spawning children,
        # do not submit jobs.
        if (itask.tdef.run_mode == RunMode.SIMULATION) or forced:
            job_conf = {"submit_num": itask.submit_num}
        else:
            job_conf = itask.jobs[-1]

        # Job status should be task status unless task is awaiting a
        # retry:
        if itask.state.status == TASK_STATUS_WAITING and itask.try_timers:
            job_status = (
                TASK_STATUS_SUBMITTED if submit_status == 0
                else TASK_STATUS_SUBMIT_FAILED
            )
        else:
            job_status = itask.state.status

        # insert job into data store
        self.data_store_mgr.insert_job(
            itask.tdef.name,
            itask.point,
            job_status,
            {
                **job_conf,
                # NOTE: the platform name may have changed since task
                # preparation started due to intelligent host (and or
                # platform) selection
                'platform': itask.platform,
            },
        )
        # update job in database
        # NOTE: the job must be added to the DB earlier so that Cylc can
        # reconnect with job submissions if the scheduler is restarted
        self.workflow_db_mgr.put_update_task_jobs(
            itask,
            {
                'submit_status': submit_status,
                'time_submit_exit': event_time,
                'job_id': itask.summary.get('submit_method_id'),
                # NOTE: the platform name may have changed since task
                # preparation started due to intelligent host (and or
                # platform) selection
                'platform_name': itask.platform['name'],
            }
        )

    def _setup_job_logs_retrieval(self, itask, event) -> None:
        """Set up remote job logs retrieval.

        For a task with a job completion event, i.e. succeeded, failed,
        (execution) retry.
        """
        if (
            event not in self.JOB_LOGS_RETRIEVAL_EVENTS
            or not is_remote_platform(itask.platform)
            or not self._get_remote_conf(itask, "retrieve job logs")
        ):
            # event does not need to be processed
            return

        id_key = EventKey(
            self.HANDLER_JOB_LOGS_RETRIEVE,
            event,
            event,
            itask.tokens.duplicate(job=itask.submit_num),
        )
        if id_key in self._event_timers:
            # event already being processed
            return

        retry_delays = self._get_remote_conf(
            itask, "retrieve job logs retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.add_event_timer(
            id_key,
            TaskActionTimer(
                TaskJobLogsRetrieveContext(
                    key=self.HANDLER_JOB_LOGS_RETRIEVE,
                    platform_name=itask.platform['name'],
                    max_size=self._get_remote_conf(
                        itask, "retrieve job logs max size"
                    ),
                ),
                retry_delays
            )
        )

    def _setup_event_mail(
        self,
        itask: 'TaskProxy',
        event: str,
        message: str,
    ) -> None:
        """Set up task event notification, by email."""
        if event not in self._get_events_conf(itask, "mail events", []):
            # event does not need to be processed
            return

        id_key = EventKey(
            self.HANDLER_MAIL,
            get_event_id(event, itask),
            message,
            itask.tokens.duplicate(job=itask.submit_num),
        )
        if id_key in self._event_timers:
            # event already being processed
            return

        self.add_event_timer(
            id_key,
            TaskActionTimer(
                TaskEventMailContext(
                    key=self.HANDLER_MAIL,
                    mail_from=self._get_events_conf(
                        itask, "from", f"notifications@{get_host()}"
                    ),
                    mail_to=self._get_events_conf(itask, "to", get_user())
                )
            )
        )

    def _setup_custom_event_handlers(
        self,
        itask: 'TaskProxy',
        event: str,
        message: str,
    ) -> None:
        """Set up custom task event handlers."""
        handlers = self._get_events_conf(itask, f'{event} handlers')
        if (
            handlers is None
            and event in self._get_events_conf(itask, 'handler events', [])
        ):
            handlers = self._get_events_conf(itask, 'handlers')
        if handlers is None:
            return
        retry_delays = self._get_events_conf(
            itask,
            'handler retry delays'
        )
        if not retry_delays:
            retry_delays = [0]
        # There can be multiple custom event handlers
        for i, handler in enumerate(handlers):
            id_key = EventKey(
                f'{self.HANDLER_CUSTOM}-{i:02d}',
                get_event_id(event, itask),
                message,
                itask.tokens.duplicate(job=itask.submit_num),
            )

            if id_key in self._event_timers:
                continue
            # Note: user@host may not always be set for a submit number, e.g.
            # on late event or if host select command fails. Use null string to
            # prevent issues in this case.
            platform_name = itask.summary['platforms_used'].get(
                itask.submit_num, ''
            )
            # Custom event handler can be a command template string
            # or a command that takes 4 arguments (classic interface)
            # Note quote() fails on None, need str(None).

            template_variables = self._get_handler_template_variables(
                itask,
                event,
                message,
                platform_name,
            )
            key1 = (id_key.handler, id_key.event)
            try:
                cmd = handler % template_variables
            except KeyError as exc:
                LOG.error(
                    f'{id_key.tokens.relative_id}'
                    f" {key1} bad template: {exc}")
                continue

            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = (f"{handler} '{event}' '{self.workflow}' "
                       f"'{itask.identity}' '{message}'")
            LOG.debug(f"[{itask}] Queueing {event} handler: {cmd}")
            self.add_event_timer(
                id_key,
                TaskActionTimer(
                    CustomTaskEventHandlerContext(key=key1, cmd=cmd),
                    retry_delays
                )
            )

    def _get_handler_template_variables(
        self,
        itask,
        event,
        message,
        platform_name,
    ):
        # fmt: off
        return {
            EventData.JobID.value:
                quote(str(itask.summary['submit_method_id'])),
            EventData.JobRunnerName.value:
                quote(str(itask.summary['job_runner_name'])),
            EventData.CyclePoint.value:
                quote(str(itask.point)),
            EventData.Event.value:
                quote(event),
            EventData.FinishTime.value:
                quote(str(itask.summary['finished_time_string'])),
            EventData.ID.value:
                quote(itask.identity),
            EventData.Message.value:
                quote(message),
            EventData.TaskName.value:
                quote(itask.tdef.name),
            EventData.PlatformName.value:
                quote(platform_name),
            EventData.UserAtHost.value:
                quote(platform_name),
            EventData.StartTime.value:
                quote(str(itask.summary['started_time_string'])),
            EventData.SubmitNum.value:
                itask.submit_num,
            EventData.SubmitTime.value:
                quote(str(itask.summary['submitted_time_string'])),
            EventData.Workflow.value:
                quote(self.workflow),
            EventData.UUID.value:
                quote(self.uuid_str),
            # BACK COMPAT: Suite, SuiteUUID deprecated
            # url:
            #     https://github.com/cylc/cylc-flow/pull/4174
            # from:
            #     Cylc 8
            # remove at:
            #     Cylc 8.x
            EventData.Suite.value:  # deprecated
                quote(self.workflow),
            EventData.SuiteUUID.value:  # deprecated
                quote(self.uuid_str),
            EventData.TryNum.value:
                itask.get_try_num(),
            # BACK COMPAT: JobID_old, JobRunnerName_old
            # url:
            #     https://github.com/cylc/cylc-flow/pull/3992
            # from:
            #     Cylc < 8
            # remove at:
            #     Cylc8.x - pending announcement of deprecation
            # next 2 (JobID_old, JobRunnerName_old) are deprecated
            EventData.JobID_old.value:
                quote(str(itask.summary['submit_method_id'])),
            EventData.JobRunnerName_old.value:
                quote(str(itask.summary['job_runner_name'])),
            # task and workflow metadata
            **get_event_handler_data(
                itask.tdef.rtconfig, self.workflow_cfg)
        }
        # fmt: on

    def _reset_job_timers(self, itask):
        """Set up poll timer and timeout for task."""

        if itask.transient:
            return

        if not itask.state(*TASK_STATUSES_ACTIVE):
            # Reset, task not active
            itask.timeout = None
            itask.poll_timer = None
            return

        ctx = (itask.submit_num, itask.state.status)
        if itask.poll_timer and itask.poll_timer.ctx == ctx:
            return
        # Set poll timer
        # Set timeout
        timeref = None  # reference time, submitted or started time
        timeout = None  # timeout in setting
        if itask.state(TASK_STATUS_RUNNING):
            timeref = itask.summary['started_time']
            timeout_key = 'execution timeout'
            # Actual timeout after all polling.
            timeout = self._get_events_conf(itask, timeout_key)
            execution_polling_intervals = list(
                self._get_workflow_platforms_conf(
                    itask, 'execution polling intervals'))
            if itask.summary[TaskEventsManager.KEY_EXECUTE_TIME_LIMIT]:
                time_limit = itask.summary[
                    TaskEventsManager.KEY_EXECUTE_TIME_LIMIT]
                time_limit_polling_intervals = itask.platform.get(
                    'execution time limit polling intervals')
                delays = self.process_execution_polling_intervals(
                    execution_polling_intervals,
                    time_limit,
                    time_limit_polling_intervals
                )
            else:
                delays = execution_polling_intervals
        else:  # if itask.state.status == TASK_STATUS_SUBMITTED:
            timeref = itask.summary['submitted_time']
            timeout_key = 'submission timeout'
            timeout = self._get_events_conf(itask, timeout_key)
            delays = list(self._get_workflow_platforms_conf(
                itask, 'submission polling intervals'))
        try:
            itask.timeout = timeref + float(timeout)
            timeout_str = intvl_as_str(timeout)
        except (TypeError, ValueError):
            itask.timeout = None
            timeout_str = None
        itask.poll_timer = TaskActionTimer(ctx=ctx, delays=delays)
        # Log timeout and polling schedule
        message = f"health: {timeout_key}={timeout_str}"
        # Attempt to group identical consecutive delays as N*DELAY,...
        if itask.poll_timer.delays:
            items = []  # [(number of item - 1, item), ...]
            for delay in itask.poll_timer.delays:
                if items and items[-1][1] == delay:
                    items[-1][0] += 1
                else:
                    items.append([0, delay])
            message += ', polling intervals='
            for num, item in items:
                if num:
                    message += '%d*' % (num + 1)
                message += '%s,' % intvl_as_str(item)
            message += '...'
        LOG.debug(f"[{itask}] {message}")
        # Set next poll time
        self.check_poll_time(itask)

    @staticmethod
    def process_execution_polling_intervals(
        polling_intervals: List[float],
        time_limit: float,
        time_limit_polling_intervals: List[float]
    ) -> List[float]:
        """Create a list of polling times.

        Args:
            (execution) polling_intervals
            (execution) time_limit
            (execution) time_limit_polling_intervals

        Examples:

        >>> this = TaskEventsManager.process_execution_polling_intervals

        # Basic example:
        >>> this([40, 35], 100, [10])
        [40, 35, 35, 10]

        # Second 40 second delay gets lopped off the list because it's after
        # the execution time limit:
        >>> this([40, 40], 60, [10])
        [40, 30, 10]

        # Expand last item in exection polling intervals to fill the
        # execution time limit:
        >>> this([5, 20], 100, [10])
        [5, 20, 20, 20, 20, 25, 10]

        # There are no execution polling intervals set - polling starts
        # at execution time limit:
        >>> this([], 10, [5])
        [15, 5]

        # We have a list of execution time limit polling intervals,
        >>> this([10], 25, [5, 6, 7, 8])
        [10, 10, 10, 6, 7, 8]
        """
        delays = polling_intervals
        if sum(delays) > time_limit:
            # Remove execution polling which would overshoot the
            # execution time limit:
            while sum(delays) > time_limit:
                del delays[-1]
        elif delays:
            # Repeat the last execution polling interval up to the execution
            # time limit:
            size = int((time_limit - sum(delays)) / delays[-1])
            delays.extend([delays[-1]] * size)

        # After the last delay before the execution time limit add the
        # delay to get to the execution_time_limit
        if len(time_limit_polling_intervals) == 1:
            time_limit_polling_intervals.append(
                time_limit_polling_intervals[0]
            )
        time_limit_polling_intervals[0] += time_limit - sum(delays)

        # After the execution time limit poll at execution time limit polling
        # intervals.
        delays += time_limit_polling_intervals
        return delays

    def add_event_timer(self, id_key: EventKey, event_timer) -> None:
        """Add a new event timer.

        Args:
            id_key (str)
            timer (TaskActionTimer)

        """
        self._event_timers[id_key] = event_timer
        self.event_timers_updated = True

    def remove_event_timer(self, id_key: EventKey) -> None:
        """Remove an event timer.

        Args:
            id_key (str)

        """
        del self._event_timers[id_key]
        self.event_timers_updated = True

    def unset_waiting_event_timer(self, id_key: EventKey) -> None:
        """Invoke unset_waiting on an event timer."""
        self._event_timers[id_key].unset_waiting()
        self.event_timers_updated = True

    def reset_bad_hosts(self):
        """Clear bad_hosts list.
        """
        if self.bad_hosts:
            LOG.info(
                'Clearing bad hosts: '
                f'{self.bad_hosts}'
            )
            self.bad_hosts.clear()

    def spawn_children(self, itask: 'TaskProxy', output: str) -> None:
        # update DB task outputs
        self.workflow_db_mgr.put_update_task_outputs(itask)
        # spawn child-tasks
        self.spawn_func(itask, output)
