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
from collections import namedtuple
from enum import Enum
from logging import DEBUG, INFO, getLevelName
import os
from shlex import quote
import shlex
from time import time
from typing import TYPE_CHECKING, Optional, Union, cast

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
    TASK_STATUS_SUCCEEDED,
    TASK_STATUS_WAITING
)
from cylc.flow.task_outputs import (
    TASK_OUTPUT_SUBMITTED, TASK_OUTPUT_STARTED, TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED, TASK_OUTPUT_SUBMIT_FAILED)
from cylc.flow.wallclock import (
    get_current_time_string,
    get_time_string_from_unix_time,
    get_seconds_as_interval_string as intvl_as_str
)
from cylc.flow.workflow_events import (
    EventData as WorkflowEventData,
    get_template_variables as get_workflow_template_variables,
    process_mail_footer,
)


if TYPE_CHECKING:
    from cylc.flow.task_proxy import TaskProxy
    from cylc.flow.scheduler import Scheduler


CustomTaskEventHandlerContext = namedtuple(
    "CustomTaskEventHandlerContext",
    ["key", "ctx_type", "cmd"])


TaskEventMailContext = namedtuple(
    "TaskEventMailContext",
    ["key", "ctx_type", "mail_from", "mail_to"])


TaskJobLogsRetrieveContext = namedtuple(
    "TaskJobLogsRetrieveContext",
    ["key", "ctx_type", "platform_name", "max_size"])


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
    except IOError as exc:
        # This happens when there is no job directory, e.g. if job host
        # selection command causes an submission failure, there will be no job
        # directory. In this case, just send the information to the log.
        LOG.exception(exc)
        LOG.info(ctx_str)
    if ctx.cmd and ctx.ret_code:
        LOG.error(ctx_str)
    elif ctx.cmd:
        LOG.debug(ctx_str)


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

       Use 'uuid_str'.
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

    def __init__(
        self, workflow, proc_pool, workflow_db_mgr, broadcast_mgr,
        xtrigger_mgr, data_store_mgr, timestamp, bad_hosts,
        reset_inactivity_timer_func
    ):
        self.workflow = workflow
        self.workflow_url = None
        self.workflow_cfg = {}
        self.uuid_str = None
        self.proc_pool = proc_pool
        self.workflow_db_mgr = workflow_db_mgr
        self.broadcast_mgr = broadcast_mgr
        self.xtrigger_mgr = xtrigger_mgr
        self.data_store_mgr = data_store_mgr
        self.mail_interval = 0.0
        self.mail_smtp = None
        self.mail_footer = None
        self.next_mail_time = None
        self.reset_inactivity_timer_func = reset_inactivity_timer_func
        # NOTE: do not mutate directly
        # use the {add,remove,unset_waiting}_event_timers methods
        self._event_timers = {}
        # NOTE: flag for DB use
        self.event_timers_updated = True
        # To be set by the task pool:
        self.spawn_func = None
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
            self.setup_event_handlers(
                itask, get_time_string_from_unix_time(now), event, msg)
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
            key1, point, name, submit_num = id_key
            if timer.is_waiting:
                continue
            # Set timer if timeout is None.
            if not timer.is_timeout_set():
                if timer.next() is None:
                    LOG.warning(
                        f"{point}/{name}/{submit_num:02d}"
                        f" handler:{key1[0]} for task event:{key1[1]} failed"
                    )
                    self.remove_event_timer(id_key)
                    continue
                # Report retries and delayed 1st try
                msg = None
                if timer.num > 1:
                    msg = (
                        f"handler:{key1[0]} for task event:{key1[1]} failed,"
                        f" retrying in {timer.delay_timeout_as_str()}"
                    )
                elif timer.delay:
                    msg = (
                        f"handler:{key1[0]} for task event:{key1[1]} will"
                        f" run after {timer.delay_timeout_as_str()}"
                    )
                if msg:
                    LOG.debug(f"{point}/{name}/{submit_num:02d} {msg}")
            # Ready to run?
            if not timer.is_delay_done() or (
                # Avoid flooding user's mail box with mail notification.
                # Group together as many notifications as possible within a
                # given interval.
                timer.ctx.ctx_type == self.HANDLER_MAIL and
                not schd.stop_mode and
                self.next_mail_time is not None and
                self.next_mail_time > now
            ):
                continue

            timer.set_waiting()
            if timer.ctx.ctx_type == self.HANDLER_CUSTOM:
                # Run custom event handlers on their own
                self.proc_pool.put_command(
                    SubProcContext(
                        (key1, submit_num),
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
            if ctx.ctx_type == self.HANDLER_MAIL:
                # Set next_mail_time if any mail sent
                self.next_mail_time = next_mail_time
                self._process_event_email(schd, ctx, id_keys)
            elif ctx.ctx_type == self.HANDLER_JOB_LOGS_RETRIEVE:
                self._process_job_logs_retrieval(schd, ctx, id_keys)

    def process_message(
        self,
        itask: 'TaskProxy',
        severity: Union[str, int],
        message: str,
        event_time: Optional[str] = None,
        flag: str = FLAG_INTERNAL,
        submit_num: Optional[int] = None,
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
            severity = cast(str, getLevelName(severity))
        lseverity = str(severity).lower()

        # Any message represents activity.
        self.reset_inactivity_timer_func()

        quiet_msg_check = False
        if (
            itask.tdef.run_mode == 'live'
            and self.workflow_db_mgr.pri_dao.message_in_db(
                itask, event_time, submit_num, message)
        ):
            quiet_msg_check = True
        if not self._process_message_check(
            itask, severity, message, event_time, flag, submit_num,
            quiet=quiet_msg_check,
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

        msg0 = message.split('/')[0]
        completed_trigger = itask.state.outputs.set_msg_trg_completion(
            message=msg0, is_completed=True)
        self.data_store_mgr.delta_task_output(itask, msg0)

        # Check the `started` event has not been missed e.g. due to
        # polling delay
        if (message not in [self.EVENT_SUBMITTED, self.EVENT_SUBMIT_FAILED,
                            self.EVENT_STARTED]
                and not itask.state.outputs.is_completed(TASK_OUTPUT_STARTED)):
            self.setup_event_handlers(
                itask, event_time,
                self.EVENT_STARTED, f'job {self.EVENT_STARTED}')
            self.spawn_func(itask, TASK_OUTPUT_STARTED)

        if message == self.EVENT_STARTED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_RUNNING)
            ):
                return True
            if itask.state.status == TASK_STATUS_PREPARING:
                # The started message must have arrived before the submitted
                # one, so assume that a successful submission occurred and act
                # accordingly. Note the submitted message is internal, whereas
                # the started message comes in on the network.
                self._process_message_submitted(itask, event_time)
                self.spawn_func(itask, TASK_OUTPUT_SUBMITTED)

            self._process_message_started(itask, event_time)
            self.spawn_func(itask, TASK_OUTPUT_STARTED)

        elif message == self.EVENT_SUCCEEDED:
            self._process_message_succeeded(itask, event_time)
            self.spawn_func(itask, TASK_OUTPUT_SUCCEEDED)
        elif message == self.EVENT_FAILED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)
            ):
                return True
            if self._process_message_failed(
                    itask, event_time, self.JOB_FAILED):
                self.spawn_func(itask, TASK_OUTPUT_FAILED)
        elif message == self.EVENT_SUBMIT_FAILED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_SUBMIT_FAILED)
            ):
                return True
            if self._process_message_submit_failed(
                itask,
                event_time,
                submit_num
            ):
                self.spawn_func(itask, TASK_OUTPUT_SUBMIT_FAILED)
        elif message == self.EVENT_SUBMITTED:
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_SUBMITTED)
            ):
                return True
            if (
                itask.state.status == TASK_STATUS_PREPARING
                or itask.tdef.run_mode == 'simulation'
            ):
                # If not in the preparing state we already assumed and handled
                # job submission under the started event above...
                # (sim mode does not have the job prep state)
                self._process_message_submitted(itask, event_time)
                self.spawn_func(itask, TASK_OUTPUT_SUBMITTED)

            # ... but either way update the job ID in the job proxy (it only
            # comes in via the submission message).
            if itask.tdef.run_mode != 'simulation':
                job_tokens = itask.tokens.duplicate(
                    job=str(itask.submit_num)
                )
                self.data_store_mgr.delta_job_attr(
                    job_tokens, 'job_id', itask.summary['submit_method_id'])

        elif message.startswith(FAIL_MESSAGE_PREFIX):
            # Task received signal.
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)
            ):
                return True
            signal = message[len(FAIL_MESSAGE_PREFIX):]
            self._db_events_insert(itask, event_time, "signaled", signal)
            self.workflow_db_mgr.put_update_task_jobs(
                itask, {"run_signal": signal})
            if self._process_message_failed(
                    itask, event_time, self.JOB_FAILED):
                self.spawn_func(itask, TASK_OUTPUT_FAILED)
        elif message.startswith(ABORT_MESSAGE_PREFIX):
            # Task aborted with message
            if (
                    flag == self.FLAG_RECEIVED
                    and itask.state.is_gt(TASK_STATUS_FAILED)
            ):
                return True
            aborted_with = message[len(ABORT_MESSAGE_PREFIX):]
            self._db_events_insert(itask, event_time, "aborted", message)
            self.workflow_db_mgr.put_update_task_jobs(
                itask, {"run_signal": aborted_with})
            if self._process_message_failed(itask, event_time, aborted_with):
                self.spawn_func(itask, TASK_OUTPUT_FAILED)
        elif message.startswith(VACATION_MESSAGE_PREFIX):
            # Task job pre-empted into a vacation state
            self._db_events_insert(itask, event_time, "vacated", message)
            itask.set_summary_time('started')  # unset
            if TimerFlags.SUBMISSION_RETRY in itask.try_timers:
                itask.try_timers[TimerFlags.SUBMISSION_RETRY].num = 0
            itask.job_vacated = True
            # Believe this and change state without polling (could poll?).
            if itask.state_reset(TASK_STATUS_SUBMITTED):
                itask.state_reset(is_queued=False)
                self.data_store_mgr.delta_task_state(itask)
                self.data_store_mgr.delta_task_queued(itask)
            self._reset_job_timers(itask)
            # We should really have a special 'vacated' handler, but given that
            # this feature can only be used on the deprecated loadleveler
            # system, we should probably aim to remove support for job vacation
            # instead. Otherwise, we should have:
            # self.setup_event_handlers(itask, event_time, 'vacated', message)
        elif completed_trigger:
            # Message of an as-yet unreported custom task output.
            # No state change.
            self.setup_event_handlers(
                itask, event_time, completed_trigger, message)
            self.spawn_func(itask, msg0)
        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            # No state change.
            LOG.debug(f"[{itask}] unhandled: {message}")
            self._db_events_insert(
                itask, event_time, (f"message {lseverity}"), message)
        if lseverity in self.NON_UNIQUE_EVENTS:
            itask.non_unique_events.update({lseverity: 1})
            self.setup_event_handlers(itask, event_time, lseverity, message)
        return None

    def _process_message_check(
        self,
        itask: 'TaskProxy',
        severity: str,
        message: str,
        event_time: str,
        flag: str,
        submit_num: int,
        quiet: bool = False,
    ) -> bool:
        """Helper for `.process_message`.

        See `.process_message` for argument list
        Check whether to process/skip message.
        Return True if `.process_message` should contine, False otherwise.
        """
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
                and
                (
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

        severity = cast(int, LOG_LEVELS.get(severity, INFO))
        # Demote log level to DEBUG if this is a message that duplicates what
        # gets logged by itask state change anyway (and not manual poll)
        if severity > DEBUG and flag != self.FLAG_POLLED and message in {
            self.EVENT_SUBMITTED, self.EVENT_STARTED, self.EVENT_SUCCEEDED,
            self.EVENT_SUBMIT_FAILED, f'{FAIL_MESSAGE_PREFIX}ERR'
        }:
            severity = DEBUG

        if not quiet:
            LOG.log(severity, f"[{itask}] {flag}{message}{timestamp}")
        return True

    def setup_event_handlers(
        self, itask: 'TaskProxy', event_time: str, event: str, message: str
    ) -> None:
        """Set up handlers for a task event."""
        if itask.tdef.run_mode != 'live':
            return
        msg = ""
        if message != f"job {event}":
            msg = message
        self._db_events_insert(itask, event_time, event, msg)
        self._setup_job_logs_retrieval(itask, event)
        self._setup_event_mail(itask, event)
        self._setup_custom_event_handlers(itask, event, message)

    def _custom_handler_callback(self, ctx, schd, id_key):
        """Callback when a custom event handler is done."""
        _, point, name, submit_num = id_key
        log_task_job_activity(ctx, schd.workflow, point, name, submit_num)
        if ctx.ret_code == 0:
            self.remove_event_timer(id_key)
        else:
            self.unset_waiting_event_timer(id_key)

    def _db_events_insert(self, itask, event_time, event="", message=""):
        """Record an event to the DB."""
        self.workflow_db_mgr.put_insert_task_events(itask, {
            "time": event_time,
            "event": event,
            "message": message})

    def _process_event_email(self, schd: 'Scheduler', ctx, id_keys) -> None:
        """Process event notification, by email."""
        if len(id_keys) == 1:
            # 1 event from 1 task
            (_, event), point, name, submit_num = id_keys[0]
            subject = "[%s/%s/%02d %s] %s" % (
                point, name, submit_num, event, schd.workflow)
        else:
            event_set = {id_key[0][1] for id_key in id_keys}
            if len(event_set) == 1:
                # 1 event from n tasks
                subject = "[%d tasks %s] %s" % (
                    len(id_keys), event_set.pop(), schd.workflow)
            else:
                # n events from n tasks
                subject = "[%d task events] %s" % (
                    len(id_keys), schd.workflow)
        cmd = ["mail", "-s", subject]
        # From: and To:
        cmd.append("-r")
        cmd.append(ctx.mail_from)
        cmd.append(ctx.mail_to)
        # STDIN for mail, tasks
        stdin_str = ""
        for id_key in sorted(id_keys):
            (_, event), point, name, submit_num = id_key
            stdin_str += "%s: %s/%s/%02d\n" % (event, point, name, submit_num)
        # STDIN for mail, event info + workflow detail
        stdin_str += "\n"
        for key in (
            WorkflowEventData.Workflow.value,
            WorkflowEventData.Host.value,
            WorkflowEventData.Port.value,
            WorkflowEventData.Owner.value,
        ):
            value = getattr(schd, key, None)
            if value:
                stdin_str += '%s: %s\n' % (key, value)

        if self.mail_footer:
            stdin_str += process_mail_footer(
                self.mail_footer,
                get_workflow_template_variables(schd, event, ''),
            )
        self._send_mail(ctx, cmd, stdin_str, id_keys, schd)

    def _send_mail(self, ctx, cmd, stdin_str, id_keys, schd):
        # SMTP server
        env = dict(os.environ)
        if self.mail_smtp:
            env["smtp"] = self.mail_smtp
        self.proc_pool.put_command(
            SubProcContext(
                ctx, cmd, env=env, stdin_str=stdin_str, id_keys=id_keys,
            ),
            callback=self._event_email_callback, callback_args=[schd])

    def _event_email_callback(self, proc_ctx, schd):
        """Call back when email notification command exits."""
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                if proc_ctx.ret_code == 0:
                    self.remove_event_timer(id_key)
                    log_ctx = SubProcContext((key1, submit_num), None)
                    log_ctx.ret_code = 0
                    log_task_job_activity(
                        log_ctx, schd.workflow, point, name, submit_num)
                else:
                    self.unset_waiting_event_timer(id_key)
            except KeyError as exc:
                LOG.exception(exc)

    def _get_events_conf(self, itask, key, default=None):
        """Return an events setting from workflow then global configuration."""
        for getter in [
                self.broadcast_mgr.get_broadcast(itask.tokens).get("events"),
                itask.tdef.rtconfig["mail"],
                itask.tdef.rtconfig["events"],
                glbl_cfg().get(["scheduler", "mail"]),
                glbl_cfg().get()["task events"],
        ]:
            try:
                value = getter.get(key)
            except (AttributeError, ItemNotFoundError, KeyError):
                pass
            else:
                if value is not None:
                    return value
        return default

    def _process_job_logs_retrieval(self, schd, ctx, id_keys):
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
        for _, point, name, submit_num in id_keys:
            # Include relevant directories, all levels needed
            includes.add("/%s" % (point))
            includes.add("/%s/%s" % (point, name))
            includes.add("/%s/%s/%02d" % (point, name, submit_num))
            includes.add("/%s/%s/%02d/**" % (point, name, submit_num))
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

    def _job_logs_retrieval_callback_255(self, proc_ctx, schd):
        """Call back when log job retrieval fails with a 255 error."""
        self.bad_hosts.add(proc_ctx.host)
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            for key in proc_ctx.cmd_kwargs['id_keys']:
                timer = self._event_timers[key]
                timer.reset()

    def _job_logs_retrieval_callback(self, proc_ctx, schd):
        """Call back when log job retrieval completes."""
        if (
            (proc_ctx.ret_code and LOG.isEnabledFor(DEBUG))
            or (proc_ctx.ret_code and proc_ctx.ret_code != 255)
        ):
            LOG.error(proc_ctx)
        else:
            LOG.debug(proc_ctx)
        for id_key in proc_ctx.cmd_kwargs["id_keys"]:
            key1, point, name, submit_num = id_key
            try:
                # All completed jobs are expected to have a "job.out".
                fnames = [JOB_LOG_OUT]
                with suppress(TypeError):
                    if key1[1] not in 'succeeded':
                        fnames.append(JOB_LOG_ERR)
                fname_oks = {}
                for fname in fnames:
                    fname_oks[fname] = os.path.exists(get_task_job_log(
                        schd.workflow, point, name, submit_num, fname))
                # All expected paths must exist to record a good attempt
                log_ctx = SubProcContext((key1, submit_num), None)
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
                    log_ctx, schd.workflow, point, name, submit_num)
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
            self.xtrigger_mgr.add_trig(
                label,
                xtrig,
                os.getenv("CYLC_WORKFLOW_RUN_DIR")
            )
            itask.state.add_xtrigger(label)
        if itask.state_reset(TASK_STATUS_WAITING):
            self.data_store_mgr.delta_task_state(itask)

    def _process_message_failed(self, itask, event_time, message):
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
                TimerFlags.EXECUTION_RETRY not in itask.try_timers
                or itask.try_timers[TimerFlags.EXECUTION_RETRY].next() is None
        ):
            # No retry lined up: definitive failure.
            if itask.state_reset(TASK_STATUS_FAILED):
                self.setup_event_handlers(
                    itask, event_time, self.EVENT_FAILED, message)
                self.data_store_mgr.delta_task_state(itask)
            no_retries = True
        else:
            # There is an execution retry lined up.
            timer = itask.try_timers[TimerFlags.EXECUTION_RETRY]
            self._retry_task(itask, timer.timeout)
            delay_msg = f"retrying in {timer.delay_timeout_as_str()}"
            LOG.warning(f"[{itask}] {delay_msg}")
            msg = f"{self.JOB_FAILED}, {delay_msg}"
            self.setup_event_handlers(
                itask, event_time, self.EVENT_RETRY, msg)
        self._reset_job_timers(itask)
        return no_retries

    def _process_message_started(self, itask, event_time):
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
        if itask.state_reset(TASK_STATUS_RUNNING):
            self.setup_event_handlers(
                itask, event_time,
                self.EVENT_STARTED, f'job {self.EVENT_STARTED}')
            self.data_store_mgr.delta_task_state(itask)
        self._reset_job_timers(itask)

        # submission was successful so reset submission try number
        if TimerFlags.SUBMISSION_RETRY in itask.try_timers:
            itask.try_timers[TimerFlags.SUBMISSION_RETRY].num = 0

    def _process_message_succeeded(self, itask, event_time):
        """Helper for process_message, handle a succeeded message."""

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
        if itask.state_reset(TASK_STATUS_SUCCEEDED):
            self.setup_event_handlers(
                itask, event_time,
                self.EVENT_SUCCEEDED, f"job {self.EVENT_SUCCEEDED}")
            self.data_store_mgr.delta_task_state(itask)
        self._reset_job_timers(itask)

    def _process_message_submit_failed(self, itask, event_time, submit_num):
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
                TimerFlags.SUBMISSION_RETRY not in itask.try_timers
                or itask.try_timers[TimerFlags.SUBMISSION_RETRY].next() is None
        ):
            # No submission retry lined up: definitive failure.
            # See github #476.
            no_retries = True
            if itask.state_reset(TASK_STATUS_SUBMIT_FAILED):
                self.setup_event_handlers(
                    itask, event_time, self.EVENT_SUBMIT_FAILED,
                    f'job {self.EVENT_SUBMIT_FAILED}')
                self.data_store_mgr.delta_task_state(itask)
        else:
            # There is a submission retry lined up.
            timer = itask.try_timers[TimerFlags.SUBMISSION_RETRY]
            self._retry_task(itask, timer.timeout, submit_retry=True)
            delay_msg = f"retrying in {timer.delay_timeout_as_str()}"
            LOG.warning(f"[{itask}] {delay_msg}")
            msg = f"job {self.EVENT_SUBMIT_FAILED}, {delay_msg}"
            self.setup_event_handlers(
                itask, event_time, self.EVENT_SUBMIT_RETRY, msg)

        # Register newly submit-failed job with the database and datastore.
        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self._insert_task_job(itask, event_time, self.JOB_SUBMIT_FAIL_FLAG)
        self.data_store_mgr.delta_job_state(
            job_tokens,
            TASK_STATUS_SUBMIT_FAILED
        )

        self._reset_job_timers(itask)

        return no_retries

    def _process_message_submitted(
        self, itask: 'TaskProxy', event_time: str
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
        if itask.tdef.run_mode == 'simulation':
            # Simulate job started as well.
            itask.set_summary_time('started', event_time)
            if itask.state_reset(TASK_STATUS_RUNNING):
                self.data_store_mgr.delta_task_state(itask)
            itask.state.outputs.set_completion(TASK_OUTPUT_STARTED, True)
            self.data_store_mgr.delta_task_output(itask, TASK_OUTPUT_STARTED)
        else:
            # Unset started and finished times in case of resubmission.
            itask.set_summary_time('started')
            itask.set_summary_time('finished')
            if itask.state.status == TASK_STATUS_PREPARING:
                # The job started message can (rarely) come in before the
                # submit command returns - in which case do not go back to
                # 'submitted'.
                if itask.state_reset(TASK_STATUS_SUBMITTED):
                    itask.state_reset(is_queued=False)
                    self.setup_event_handlers(
                        itask,
                        event_time,
                        self.EVENT_SUBMITTED,
                        f'job {self.EVENT_SUBMITTED}',
                    )
                    self.data_store_mgr.delta_task_state(itask)
                    self.data_store_mgr.delta_task_queued(itask)
                self._reset_job_timers(itask)

        # Register the newly submitted job with the database and datastore.
        # Do after itask has changed state
        self._insert_task_job(itask, event_time, self.JOB_SUBMIT_SUCCESS_FLAG)
        job_tokens = itask.tokens.duplicate(job=str(itask.submit_num))
        self.data_store_mgr.delta_job_time(
            job_tokens,
            'submitted',
            event_time,
        )
        if itask.tdef.run_mode == 'simulation':
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
        submit_status: int
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
        job_conf = itask.jobs[-1]

        # insert job into data store
        self.data_store_mgr.insert_job(
            itask.tdef.name,
            itask.point,
            itask.state.status,
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

    def _setup_job_logs_retrieval(self, itask, event):
        """Set up remote job logs retrieval.

        For a task with a job completion event, i.e. succeeded, failed,
        (execution) retry.
        """
        id_key = (
            (self.HANDLER_JOB_LOGS_RETRIEVE, event),
            str(itask.point), itask.tdef.name, itask.submit_num)
        events = (self.EVENT_FAILED, self.EVENT_RETRY, self.EVENT_SUCCEEDED)
        if (
            event not in events or
            not is_remote_platform(itask.platform) or
            not self._get_remote_conf(itask, "retrieve job logs") or
            id_key in self._event_timers
        ):
            return
        retry_delays = self._get_remote_conf(
            itask, "retrieve job logs retry delays")
        if not retry_delays:
            retry_delays = [0]
        self.add_event_timer(
            id_key,
            TaskActionTimer(
                TaskJobLogsRetrieveContext(
                    self.HANDLER_JOB_LOGS_RETRIEVE,  # key
                    self.HANDLER_JOB_LOGS_RETRIEVE,  # ctx_type
                    itask.platform['name'],
                    self._get_remote_conf(itask, "retrieve job logs max size"),
                ),
                retry_delays
            )
        )

    def _setup_event_mail(self, itask, event):
        """Set up task event notification, by email."""
        if event in self.NON_UNIQUE_EVENTS:
            key1 = (
                self.HANDLER_MAIL,
                '%s-%d' % (event, itask.non_unique_events[event] or 1)
            )
        else:
            key1 = (self.HANDLER_MAIL, event)
        id_key = (key1, str(itask.point), itask.tdef.name, itask.submit_num)
        if (id_key in self._event_timers or
                event not in self._get_events_conf(itask, "mail events", [])):
            return

        self.add_event_timer(
            id_key,
            TaskActionTimer(
                TaskEventMailContext(
                    self.HANDLER_MAIL,  # key
                    self.HANDLER_MAIL,  # ctx_type
                    self._get_events_conf(  # mail_from
                        itask,
                        "from",
                        "notifications@" + get_host(),
                    ),
                    self._get_events_conf(itask, "to", get_user())  # mail_to
                )
            )
        )

    def _setup_custom_event_handlers(self, itask, event, message):
        """Set up custom task event handlers."""
        handlers = self._get_events_conf(itask, f'{event} handlers')
        if (handlers is None and
                event in self._get_events_conf(itask, 'handler events', [])):
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
            if event in self.NON_UNIQUE_EVENTS:
                key1 = (
                    f'{self.HANDLER_CUSTOM}-{i:02d}',
                    f'{event}-{itask.non_unique_events[event] or 1:d}'
                )
            else:
                key1 = (f'{self.HANDLER_CUSTOM}-{i:02d}', event)
            id_key = (
                key1, str(itask.point), itask.tdef.name, itask.submit_num)
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
            try:
                cmd = handler % template_variables
            except KeyError as exc:
                LOG.error(
                    f"{itask.point}/{itask.tdef.name}/{itask.submit_num:02d} "
                    f"{key1} bad template: {exc}")
                continue

            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = (f"{handler} '{event}' '{self.workflow}' "
                       f"'{itask.identity}' '{message}'")
            LOG.debug(f"[{itask}] Queueing {event} handler: {cmd}")
            self.add_event_timer(
                id_key,
                TaskActionTimer(
                    CustomTaskEventHandlerContext(
                        key1,
                        self.HANDLER_CUSTOM,
                        cmd,
                    ),
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
            timeout = self._get_events_conf(itask, timeout_key)
            delays = list(self._get_workflow_platforms_conf(
                itask, 'execution polling intervals'))
            if itask.summary[self.KEY_EXECUTE_TIME_LIMIT]:
                time_limit = itask.summary[self.KEY_EXECUTE_TIME_LIMIT]
                time_limit_delays = itask.platform.get(
                    'execution time limit polling intervals')
                if sum(delays) > time_limit:
                    # Remove excessive polling before time limit
                    while sum(delays) > time_limit:
                        del delays[-1]
                else:
                    # Fill up the gap before time limit
                    if delays:
                        size = int((time_limit - sum(delays)) / delays[-1])
                        delays.extend([delays[-1]] * size)
                time_limit_delays[0] += time_limit - sum(delays)
                delays += time_limit_delays
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
        LOG.info(f"[{itask}] {message}")
        # Set next poll time
        self.check_poll_time(itask)

    def add_event_timer(self, id_key, event_timer):
        """Add a new event timer.

        Args:
            id_key (str)
            timer (TaskActionTimer)

        """
        self._event_timers[id_key] = event_timer
        self.event_timers_updated = True

    def remove_event_timer(self, id_key):
        """Remove an event timer.

        Args:
            id_key (str)

        """
        del self._event_timers[id_key]
        self.event_timers_updated = True

    def unset_waiting_event_timer(self, id_key):
        """Invoke unset_waiting on an event timer.

        Args:
            key (str)

        """
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
