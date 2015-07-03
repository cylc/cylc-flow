#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import Queue
import os
import re
import socket
import time
from copy import copy
from random import randrange
from collections import deque
from logging import getLogger, CRITICAL, ERROR, WARNING, INFO, DEBUG
from pipes import quote
import shlex
from shutil import rmtree
import traceback
from isodatetime.timezone import get_local_time_zone

from cylc.mkdir_p import mkdir_p
from cylc.task_state import task_state
from cylc.cfgspec.globalcfg import GLOBAL_CFG
import cylc.cycling.iso8601
from cylc.cycling.loader import get_interval_cls, get_point_relative
from cylc.envvar import expandvars
import cylc.flags as flags
from cylc.wallclock import (
    get_current_time_string,
    get_time_string_from_unix_time,
    get_seconds_as_interval_string,
    RE_DATE_TIME_FORMAT_EXTENDED
)
from cylc.network.task_msgqueue import TaskMessageServer
from cylc.host_select import get_task_host
from cylc.job_file import JOB_FILE
from cylc.job_host import RemoteJobHostManager
from cylc.batch_sys_manager import BATCH_SYS_MANAGER
from cylc.outputs import outputs
from cylc.owner import is_remote_user, user
from cylc.poll_timer import PollTimer
from cylc.prerequisites.prerequisites import prerequisites
from cylc.prerequisites.plain_prerequisites import plain_prerequisites
from cylc.prerequisites.conditionals import conditional_prerequisites
from cylc.suite_host import is_remote_host, get_suite_host
from parsec.util import pdeepcopy, poverride
from cylc.mp_pool import SuiteProcPool, SuiteProcContext
from cylc.rundb import CylcSuiteDAO
from cylc.task_id import TaskID
from cylc.task_message import TaskMessage
from cylc.task_output_logs import logfiles


class TryState(object):
    """Represent the current state of a (re)try."""

    def __init__(self, ctx=None, delays=None):
        self.ctx = ctx
        self.delays = []
        if delays:
            self.delays += delays
        self.num = 1
        self.delay = None
        self.timeout = None

    def delay_as_seconds(self):
        """Return the delay as PTnS, where n is number of seconds."""
        return get_seconds_as_interval_string(self.delay)

    def is_delay_done(self, now=None):
        """Is timeout done?"""
        if self.timeout is None:
            return False
        if now is None:
            now = time.time()
        if now > self.timeout:
            return True
        else:
            return False

    def next(self):
        """Return the next retry delay if there is one, or None otherwise."""
        try:
            self.delay = self.delays[self.num - 1]
        except IndexError:
            return None
        else:
            self.timeout = time.time() + self.delay
            self.num += 1
            return self.delay

    def timeout_as_str(self):
        """Return the timeout as an ISO8601 date-time string."""
        return get_time_string_from_unix_time(self.timeout)


class TaskProxySequenceBoundsError(ValueError):
    """Error on TaskProxy.__init__ with out of sequence bounds start point."""

    def __str__(self):
        return "Not loading %s (out of sequence bounds)" % self.args[0]


class TaskProxy(object):
    """The task proxy."""

    # RETRY LOGIC:
    #  1) ABSOLUTE SUBMIT NUMBER increments every time a task is
    #  submitted, manually or automatically by (submission or execution)
    # retries; whether or not the task actually begins executing, and is
    # appended to the task log root filename.
    #  2) SUBMISSION TRY NUMBER increments when task job submission
    # fails, if submission retries are configured, but resets to 1 if
    # the task begins executing; and is used for accounting purposes.
    #  3) EXECUTION TRY NUMBER increments only when task execution fails,
    # if execution retries are configured; and is passed to task
    # environments to allow changed behaviour after previous failures.

    # Format string for single line output
    JOB_LOG_FMT_1 = "%(timestamp)s [%(cmd_type)s %(attr)s] %(mesg)s"
    # Format string for multi-line output
    JOB_LOG_FMT_M = "%(timestamp)s [%(cmd_type)s %(attr)s]\n\n%(mesg)s\n"

    EVENT_HANDLER = "event-handler"
    EVENT_MAIL = "event-mail"
    JOB_KILL = "job-kill"
    JOB_LOGS_RETRIEVE = "job-logs-retrieve"
    JOB_POLL = "job-poll"
    JOB_SUBMIT = SuiteProcPool.JOB_SUBMIT
    POLL_SUFFIX_RE = re.compile(
        ' at (' + RE_DATE_TIME_FORMAT_EXTENDED + '|unknown-time)$')

    LOGGING_LVL_OF = {
        "INFO": INFO,
        "NORMAL": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
        "DEBUG": DEBUG,
    }

    TABLE_TASK_JOBS = CylcSuiteDAO.TABLE_TASK_JOBS
    TABLE_TASK_JOB_LOGS = CylcSuiteDAO.TABLE_TASK_JOB_LOGS
    TABLE_TASK_EVENTS = CylcSuiteDAO.TABLE_TASK_EVENTS
    TABLE_TASK_STATES = CylcSuiteDAO.TABLE_TASK_STATES

    event_handler_env = {}
    stop_sim_mode_job_submission = False

    @classmethod
    def get_job_log_dir(
            cls, suite, task_name, task_point, submit_num="NN", rel=False):
        """Return the latest job log path on the suite host."""
        try:
            submit_num = "%02d" % submit_num
        except TypeError:
            pass
        if rel:
            return os.path.join(str(task_point), task_name, submit_num)
        else:
            suite_job_log_dir = GLOBAL_CFG.get_derived_host_item(
                suite, "suite job log directory")
            return os.path.join(
                suite_job_log_dir, str(task_point), task_name, submit_num)

    def __init__(
            self, tdef, start_point, initial_state, stop_point=None,
            is_startup=False, validate_mode=False, submit_num=0,
            is_reload=False):
        self.tdef = tdef
        if submit_num is None:
            self.submit_num = 0
        else:
            self.submit_num = submit_num
        self.validate_mode = validate_mode

        if is_startup:
            # adjust up to the first on-sequence cycle point
            adjusted = []
            for seq in self.tdef.sequences:
                adj = seq.get_first_point(start_point)
                if adj:
                    # may be None if out of sequence bounds
                    adjusted.append(adj)
            if not adjusted:
                # This task is out of sequence bounds
                raise TaskProxySequenceBoundsError(self.tdef.name)
            self.point = min(adjusted)
            self.cleanup_cutoff = self.tdef.get_cleanup_cutoff_point(
                self.point, self.tdef.intercycle_offsets)
            self.identity = TaskID.get(self.tdef.name, self.point)
        else:
            self.point = start_point
            self.cleanup_cutoff = self.tdef.get_cleanup_cutoff_point(
                self.point, self.tdef.intercycle_offsets)
            self.identity = TaskID.get(self.tdef.name, self.point)

        # prerequisites
        self.prerequisites = prerequisites(self.tdef.start_point)
        self.suicide_prerequisites = prerequisites(self.tdef.start_point)
        self._add_prerequisites(self.point)
        self.point_as_seconds = None

        self.logfiles = logfiles()
        for lfile in self.tdef.rtconfig['extra log files']:
            self.logfiles.add_path(lfile)

        # outputs
        self.outputs = outputs(self.identity)
        for outp in self.tdef.outputs:
            msg = outp.get(self.point)
            if not self.outputs.exists(msg):
                self.outputs.add(msg)
        self.outputs.register()

        self.external_triggers = {}
        for ext in self.tdef.external_triggers:
            # set unsatisfied
            self.external_triggers[ext] = False

        # Manually inserted tasks may have a final cycle point set.
        self.stop_point = stop_point

        self.job_conf = None
        self.state = task_state(initial_state)
        self.state_before_held = None  # state before being held
        self.hold_on_retry = False
        self.manual_trigger = False
        self.is_manual_submit = False

        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

        self.submitted_time = None
        self.started_time = None
        self.finished_time = None
        self.summary = {
            'latest_message': "",
            'submitted_time': None,
            'submitted_time_string': None,
            'submit_num': self.submit_num,
            'started_time': None,
            'started_time_string': None,
            'finished_time': None,
            'finished_time_string': None,
            'name': self.tdef.name,
            'description': self.tdef.rtconfig['description'],
            'title': self.tdef.rtconfig['title'],
            'label': str(self.point),
            'logfiles': self.logfiles.get_paths()
        }
        self.job_file_written = False

        self.retries_configured = False

        self.run_try_state = TryState()
        self.sub_try_state = TryState()
        self.event_handler_try_states = {}

        self.message_queue = TaskMessageServer()
        self.db_inserts_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_JOB_LOGS: [],
            self.TABLE_TASK_STATES: [],
            self.TABLE_TASK_EVENTS: [],
        }
        self.db_updates_map = {
            self.TABLE_TASK_JOBS: [],
            self.TABLE_TASK_STATES: [],
        }

        # TODO - should take suite name from config!
        self.suite_name = os.environ['CYLC_SUITE_NAME']

        # In case task owner and host are needed by _db_events_insert()
        # for pre-submission events, set their initial values as if
        # local (we can't know the correct host prior to this because
        # dynamic host selection could be used).
        self.task_host = 'localhost'
        self.task_owner = None
        self.user_at_host = self.task_host

        self.submit_method_id = None
        self.batch_sys_name = None
        self.job_vacated = False

        self.submission_poll_timer = None
        self.execution_poll_timer = None

        self.logger = getLogger("main")

        # An initial db state entry is created at task proxy init. On reloading
        # or restarting the suite, the task proxies already have this db entry.
        if not self.validate_mode and not is_reload and self.submit_num == 0:
            self.db_inserts_map[self.TABLE_TASK_STATES].append({
                "time_created": get_current_time_string(),
                "time_updated": get_current_time_string(),
                "try_num": self.run_try_state.num,
                "status": self.state.get_status()})

        if not self.validate_mode and self.submit_num > 0:
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": get_current_time_string(),
                "status": self.state.get_status()})

        self.reconfigure_me = False
        self.event_hooks = None
        self.sim_mode_run_length = None
        self.set_from_rtconfig()
        self.delayed_start_str = None
        self.delayed_start = None
        self.expire_time_str = None
        self.expire_time = None

    def _add_prerequisites(self, point):
        """Add task prerequisites."""
        # NOTE: Task objects hold all triggers defined for the task
        # in all cycling graph sections in this data structure:
        #     self.triggers[sequence] = [list of triggers for this
        #     sequence]
        # The list of triggers associated with sequenceX will only be
        # used by a particular task if the task's cycle point is a
        # valid member of sequenceX's sequence of cycle points.

        # 1) non-conditional triggers
        ppre = plain_prerequisites(self.identity, self.tdef.start_point)
        spre = plain_prerequisites(self.identity, self.tdef.start_point)

        if self.tdef.sequential:
            # For tasks declared 'sequential' we automatically add a
            # previous-instance inter-cycle trigger, and adjust the
            # cleanup cutoff (determined by inter-cycle triggers)
            # accordingly.
            p_next = None
            adjusted = []
            for seq in self.tdef.sequences:
                nxt = seq.get_next_point(self.point)
                if nxt:
                    # may be None if beyond the sequence bounds
                    adjusted.append(nxt)
            if adjusted:
                p_next = min(adjusted)
                if (self.cleanup_cutoff is not None and
                        self.cleanup_cutoff < p_next):
                    self.cleanup_cutoff = p_next

            p_prev = None
            adjusted = []
            for seq in self.tdef.sequences:
                prv = seq.get_nearest_prev_point(self.point)
                if prv:
                    # may be None if out of sequence bounds
                    adjusted.append(prv)
            if adjusted:
                p_prev = max(adjusted)
                ppre.add(TaskID.get(self.tdef.name, p_prev) + ' succeeded')

        for sequence in self.tdef.triggers:
            for trig in self.tdef.triggers[sequence]:
                if not sequence.is_valid(self.point):
                    # This trigger is not used in current cycle
                    continue
                if (trig.graph_offset_string is None or
                        (get_point_relative(
                            trig.graph_offset_string, point) >=
                         self.tdef.start_point)):
                    # i.c.t. can be None after a restart, if one
                    # is not specified in the suite definition.

                    message, prereq_point = trig.get(point)
                    prereq_offset = prereq_point - point
                    if (prereq_offset > get_interval_cls().get_null() and
                            (self.tdef.max_future_prereq_offset is None or
                             prereq_offset >
                             self.tdef.max_future_prereq_offset)):
                        self.tdef.max_future_prereq_offset = prereq_offset

                    if trig.suicide:
                        spre.add(message)
                    else:
                        ppre.add(message)

        self.prerequisites.add_requisites(ppre)
        self.suicide_prerequisites.add_requisites(spre)

        # 2) conditional triggers
        for sequence in self.tdef.cond_triggers.keys():
            for ctrig, exp in self.tdef.cond_triggers[sequence]:
                key = ctrig.keys()[0]
                if not sequence.is_valid(self.point):
                    # This trigger is not valid for current cycle (see NOTE
                    # just above)
                    continue
                cpre = conditional_prerequisites(
                    self.identity, self.tdef.start_point)
                for label in ctrig:
                    trig = ctrig[label]
                    if trig.graph_offset_string is not None:
                        is_less_than_start = (
                            get_point_relative(
                                trig.graph_offset_string, point) <
                            self.tdef.start_point
                        )
                        cpre.add(trig.get(point)[0], label, is_less_than_start)
                    else:
                        cpre.add(trig.get(point)[0], label)
                cpre.set_condition(exp)
                if ctrig[key].suicide:
                    self.suicide_prerequisites.add_requisites(cpre)
                else:
                    self.prerequisites.add_requisites(cpre)

    def log(self, lvl=INFO, msg=""):
        """Log a message of this task proxy."""
        msg = "[%s] -%s" % (self.identity, msg)
        self.logger.log(lvl, msg)

    def command_log(self, ctx):
        """Log an activity for a job of this task proxy."""
        submit_num = "NN"
        if isinstance(ctx.cmd_type, tuple):  # An event handler
            submit_num = ctx.cmd_type[-1]
        job_log_dir = self.get_job_log_dir(
            self.suite_name, self.tdef.name, self.point, submit_num)
        handle = open(os.path.join(job_log_dir, "job-activity.log"), "a")
        for attr in "cmd", "ret_code", "out", "err":
            value = getattr(ctx, attr, None)
            if value is not None and str(value).strip():
                if attr == "cmd" and isinstance(value, list):
                    mesg = " ".join(quote(item) for item in value)
                else:
                    mesg = str(value).strip()
                if attr == "cmd":
                    if ctx.cmd_kwargs.get("stdin_file_path"):
                        mesg += " <%s" % quote(
                            ctx.cmd_kwargs.get("stdin_file_path"))
                    elif ctx.cmd_kwargs.get("stdin_str"):
                        mesg += " <<<%s" % quote(
                            ctx.cmd_kwargs.get("stdin_str"))
                if getattr(ctx, "ret-code", None):
                    self.log(ERROR, mesg)
                else:
                    self.log(DEBUG, mesg)
                if len(mesg.splitlines()) > 1:
                    fmt = self.JOB_LOG_FMT_M
                else:
                    fmt = self.JOB_LOG_FMT_1
                if not mesg.endswith("\n"):
                    mesg += "\n"
                handle.write(fmt % {
                    "timestamp": ctx.timestamp,
                    "cmd_type": ctx.cmd_type,
                    "attr": attr,
                    "mesg": mesg})
        handle.close()

    def _db_events_insert(self, event="", message=""):
        """Record an event to the DB."""
        self.db_inserts_map[self.TABLE_TASK_EVENTS].append({
            "time": get_current_time_string(),
            "event": event,
            "message": message,
            "misc": self.user_at_host})

    def retry_delay_done(self):
        """Is retry delay done? Can I retry now?"""
        now = time.time()
        return (self.run_try_state.is_delay_done(now) or
                self.sub_try_state.is_delay_done(now))

    def ready_to_run(self):
        """Is this task ready to run?"""
        ready = (
            (
                self.state.is_currently('queued') or
                (
                    self.state.is_currently('waiting') and
                    self.prerequisites.all_satisfied() and
                    all(self.external_triggers.values())
                ) or
                (
                    self.state.is_currently('submit-retrying', 'retrying') and
                    self.retry_delay_done()
                )
            ) and self.start_time_reached()
        )
        if ready and self.has_expired():
            self.log(WARNING, 'Task expired (skipping job).')
            self.handle_event('expired', 'Task expired (skipping job).')
            self.reset_state_expired()
            return False
        return ready

    def get_point_as_seconds(self):
        """Compute and store my cycle point as seconds."""
        if self.point_as_seconds is None:
            iso_timepoint = cylc.cycling.iso8601.point_parse(str(self.point))
            self.point_as_seconds = int(iso_timepoint.get(
                "seconds_since_unix_epoch"))
            if iso_timepoint.time_zone.unknown:
                utc_offset_hours, utc_offset_minutes = (
                    get_local_time_zone())
                utc_offset_in_seconds = (
                    3600 * utc_offset_hours + 60 * utc_offset_minutes)
                self.point_as_seconds += utc_offset_in_seconds
        return self.point_as_seconds

    def get_offset_as_seconds(self, offset):
        """Return an ISO interval as seconds."""
        iso_offset = cylc.cycling.iso8601.interval_parse(str(offset))
        return int(iso_offset.get_seconds())

    def start_time_reached(self):
        """Has this task reached its clock trigger time?"""
        if self.tdef.clocktrigger_offset is None:
            return True
        if self.delayed_start is None:
            self.delayed_start = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.clocktrigger_offset))
            self.delayed_start_str = get_time_string_from_unix_time(
                self.delayed_start)
        return time.time() > self.delayed_start

    def has_expired(self):
        """Is this task past its use-by date?"""
        if self.tdef.expiration_offset is None:
            return False
        if self.expire_time is None:
            self.expire_time = (
                self.get_point_as_seconds() +
                self.get_offset_as_seconds(self.tdef.expiration_offset))
            self.expire_time_str = get_time_string_from_unix_time(
                self.expire_time)
        return time.time() > self.expire_time
 
    def get_resolved_dependencies(self):
        """report who I triggered off"""
        # Used by the test-battery log comparator
        dep = []
        satby = self.prerequisites.get_satisfied_by()
        for label in satby.keys():
            dep.append(satby[label])
        # order does not matter here; sort to allow comparison with
        # reference run task with lots of near-simultaneous triggers.
        dep.sort()
        return dep

    def unset_outputs(self):
        """Remove special output messages.

        These are added for use in triggering off special states:
          failed, submit-failed, expired
        If the task state is later reset, these must be removed or they will
        seen as incomplete outputs when the task finishes.
        """
        self.hold_on_retry = False
        for state in ["failed", "submit-failed", "expired"]:
            msg = "%s %s" % (self.identity, state)
            if self.outputs.exists(msg):
                self.outputs.remove(msg)

    def turn_off_timeouts(self):
        """Turn off submission and execution timeouts."""
        self.submission_timer_timeout = None
        self.execution_timer_timeout = None

    def reset_state_ready(self):
        """Reset state to "ready"."""
        self.set_status('waiting')
        self._db_events_insert(event="reset to ready")
        self.prerequisites.set_all_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_expired(self):
        """Reset state to "expired"."""
        self.set_status('expired')
        self._db_events_insert(event="reset to expired")
        self.prerequisites.set_all_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()
        self.outputs.add(self.identity + ' expired', completed=True)

    def reset_state_waiting(self):
        """Reset state to "waiting".

        Waiting and all prerequisites UNsatisified.

        """
        self.set_status('waiting')
        self._db_events_insert(event="reset to waiting")
        self.prerequisites.set_all_unsatisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_incomplete()

    def reset_state_succeeded(self, manual=True):
        """Reset state to succeeded.

        All prerequisites satisified and all outputs complete.

        """
        self.set_status('succeeded')
        if manual:
            self._db_events_insert(event="reset to succeeded")
        else:
            # Artificially set to succeeded but not by the user. E.g. by
            # the purge algorithm and when reloading task definitions.
            self._db_events_insert(event="set to succeeded")
        self.prerequisites.set_all_satisfied()
        self.unset_outputs()
        self.turn_off_timeouts()
        self.outputs.set_all_completed()

    def reset_state_failed(self):
        """Reset state to "failed".

        All prerequisites satisified and no outputs complete

        """
        self.set_status('failed')
        self._db_events_insert(event="reset to failed")
        self.prerequisites.set_all_satisfied()
        self.hold_on_retry = False
        self.outputs.set_all_incomplete()
        # set a new failed output just as if a failure message came in
        self.turn_off_timeouts()
        self.outputs.add(self.identity + ' failed', completed=True)

    def reset_state_held(self):
        """Reset state to "held"."""
        if self.state.is_currently(
                'waiting', 'queued', 'submit-retrying', 'retrying'):
            self.state_before_held = task_state(self.state.get_status())
            self.set_status('held')
            self.turn_off_timeouts()
            self._db_events_insert(event="reset to held")
            self.log(INFO, '%s => held' % self.state_before_held.get_status())
        elif self.state.is_currently('submitted', 'running'):
            self.hold_on_retry = True

    def reset_state_unheld(self, stop_point=None):
        """Reset state to state before being "held".

        If stop_point is not None, don't release task if it is beyond the stop
        cycle point.

        """
        self.hold_on_retry = False
        if (not self.state.is_currently('held') or
                stop_point and self.point > stop_point):
            return
        if self.state_before_held is None:
            return self.reset_state_waiting()
        old_status = self.state_before_held.get_status()
        self.set_status(old_status)
        self.state_before_held = None
        self._db_events_insert(event="reset to %s" % (old_status))
        self.log(INFO, 'held => %s' % (old_status))

    def job_submission_callback(self, result):
        """Callback on job submission."""
        if result.out is not None:
            out = ""
            for line in result.out.splitlines(True):
                if line.startswith(
                        BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID + "="):
                    self.submit_method_id = line.strip().replace(
                        BATCH_SYS_MANAGER.CYLC_BATCH_SYS_JOB_ID + "=", "")
                else:
                    out += line
            result.out = out
        self.command_log(result)

        if result.ret_code == SuiteProcPool.JOB_SKIPPED_FLAG:
            return
        elif result.ret_code:
            return self.job_submission_failed()

        now = get_current_time_string()
        if self.submit_method_id:
            self.log(INFO, 'submit_method_id=' + self.submit_method_id)
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": now,
                "submit_method_id": self.submit_method_id})
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "time_submit_exit": now,
                "submit_status": 0,
                "batch_sys_job_id": self.submit_method_id})
        else:
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "time_submit_exit": now,
                "submit_status": 0})
        self.job_submission_succeeded()

    def job_poll_callback(self, result):
        """Callback on job poll."""
        self.command_log(result)
        if result.ret_code:  # non-zero exit status
            self.summary['latest_message'] = 'poll failed'
            self.log(WARNING, 'job(%02d) poll failed' % self.submit_num)
            flags.iflag = True
        elif self.state.is_currently('submitted', 'running'):
            # poll results emulate task messages
            for line in result.out.splitlines():
                if line.startswith('polled %s' % (self.identity)):
                    self.process_incoming_message(('NORMAL', line))
                    break
        else:
            # Poll results can come in after a task finishes
            msg = "Ignoring late poll result: task not active"
            self.command_log(SuiteProcContext(
                self.JOB_POLL, None,
                err="Ignoring late poll result: task not active",))

    def job_kill_callback(self, result):
        """Callback on job kill."""
        self.command_log(result)
        if result.ret_code:  # non-zero exit status
            self.summary['latest_message'] = 'kill failed'
            self.log(WARNING, 'job(%02d) kill failed' % self.submit_num)
            flags.iflag = True
        elif self.state.is_currently('submitted'):
            self.log(INFO, 'job(%02d) killed' % self.submit_num)
            self.job_submission_failed()
        elif self.state.is_currently('running'):
            self.log(INFO, 'job(%02d) killed' % self.submit_num)
            self.job_execution_failed()
        else:
            msg = ('ignoring job kill result, unexpected task state: %s'
                   % self.state.get_status())
            self.log(WARNING, msg)

    def event_handler_callback(self, result):
        """Callback when event handler is done."""
        self.command_log(result)
        if result.cmd_type not in self.event_handler_try_states:
            return
        try_state = self.event_handler_try_states.pop(result.cmd_type)
        if result.ret_code == 0:
            if result.cmd_type[0] == self.JOB_LOGS_RETRIEVE:
                try:
                    submit_num = int(result.cmd_type[2])
                except ValueError:
                    pass
                else:
                    self.register_job_logs(submit_num, result)
        elif try_state.next() is None:
            self.log(ERROR, "event handler failed:\n\t%s" % result.cmd)
        else:
            self.log(
                WARNING,
                "event handler failed, retrying in %s (after %s):\n\t%s" % (
                    try_state.delay_as_seconds(),
                    try_state.timeout_as_str(),
                    result.cmd))
            self.event_handler_try_states[result.cmd_type] = try_state

    def handle_event(
            self, event, message, db_update=True, db_event=None, db_msg=None):
        """Call event handler."""
        # extra args for inconsistent use between events, logging, and db
        # updates
        db_event = db_event or event
        if db_update:
            self._db_events_insert(event=db_event, message=db_msg)

        if self.tdef.run_mode != 'live':
            return

        self.retrieve_job_logs(event, message)
        self.send_event_mail(event, message)
        self.call_event_handlers(event, message)

    def retrieve_job_logs(self, event, _=None):
        """Retrieve remote job logs."""
        key = (self.JOB_LOGS_RETRIEVE, event, "%02d" % self.submit_num)
        if (key in self.event_handler_try_states or
                event not in ["failed", "retry", "succeeded"]):
            return
        if self.user_at_host in [user + '@localhost', 'localhost']:
            self.register_job_logs(self.submit_num)
            return
        conf = self.tdef.rtconfig["remote"]
        if not conf["retrieve job logs"]:
            return
        source = (
            self.user_at_host + ":" +
            os.path.dirname(self.job_conf["job file path"]))
        cmd = ["cylc", self.JOB_LOGS_RETRIEVE]
        if conf["retrieve job logs max size"]:
            cmd.append("--max-size=%s" % conf["retrieve job logs max size"])
        cmd += [source, os.path.dirname(self.job_conf["local job file path"])]
        ctx = SuiteProcContext(key, cmd)
        try_state = TryState(ctx, conf["retrieve job logs retry delays"])
        self.event_handler_try_states[key] = try_state
        if try_state.next() is None or try_state.is_delay_done():
            try_state.timeout = None
            SuiteProcPool.get_inst().put_command(
                ctx, self.event_handler_callback)
        else:
            self.log(
                INFO,
                "%s will run after %s (after %s):\n\t%s" % (
                    self.JOB_LOGS_RETRIEVE,
                    try_state.delay_as_seconds(),
                    try_state.timeout_as_str(),
                    ctx.cmd))

    def send_event_mail(self, event, message):
        """Event notification, by email."""
        key = (self.EVENT_MAIL, event, "%02d" % self.submit_num)
        conf = self.tdef.rtconfig["events"]
        if (key in self.event_handler_try_states
                or event not in conf["mail events"]):
            return

        names = [self.suite_name, str(self.point), self.tdef.name]
        if self.submit_num:
            names.append("%02d" % self.submit_num)
        subject = "[%(event)s] %(names)s" % {
            "event": event, "names": ".".join(names)}
        cmd = ["mail", "-s", subject]
        # From:
        if conf["mail from"]:
            cmd += ["-r", conf["mail from"]]
        else:
            cmd += ["-r", "notifications@" + get_suite_host()]
        # To:
        if conf["mail to"]:
            cmd.append(conf["mail to"])
        else:
            cmd.append(user)
        # Mail message
        stdin_str = "%s: %s\n" % (subject, message)
        # SMTP server
        env = None
        if conf["mail smtp"]:
            env = dict(os.environ)
            env["smtp"] = conf["mail smtp"]

        ctx = SuiteProcContext(key, cmd, env=env, stdin_str=stdin_str)
        try_state = TryState(ctx, conf["mail retry delays"])
        self.event_handler_try_states[key] = try_state
        if try_state.next() is None or try_state.is_delay_done():
            try_state.timeout = None
            SuiteProcPool.get_inst().put_command(
                ctx, self.event_handler_callback)
        else:
            self.log(
                INFO,
                "%s will run after %s (after %s):\n\t%s" % (
                    self.EVENT_MAIL,
                    try_state.delay_as_seconds(),
                    try_state.timeout_as_str(),
                    ctx.cmd))

    def call_event_handlers(self, event, message, only_list=None):
        """Call custom event handlers."""
        conf = self.tdef.rtconfig["events"]
        handlers = []
        if self.event_hooks[event + ' handler']:
            handlers = self.event_hooks[event + ' handler']
        elif conf["handlers"] and event in conf['handler events']:
            handlers = self.tdef.rtconfig["events"]["handlers"]
        env = None
        for i, handler in enumerate(handlers):
            key = (
                "%s-%02d" % (self.EVENT_HANDLER, i),
                event,
                "%02d" % self.submit_num)
            if key in self.event_handler_try_states or (
                    only_list and i not in only_list):
                continue
            cmd = handler % {
                "event": quote(event),
                "suite": quote(self.suite_name),
                "point": quote(str(self.point)),
                "name": quote(self.tdef.name),
                "submit_num": self.submit_num,
                "id": quote(self.identity),
                "message": quote(message),
            }
            if cmd == handler:
                # Nothing substituted, assume classic interface
                cmd = "%s '%s' '%s' '%s' '%s'" % (
                    handler, event, self.suite_name, self.identity, message)
            self.log(DEBUG, "Queueing %s handler: %s" % (event, cmd))
            if env is None and TaskProxy.event_handler_env:
                env = dict(os.environ)
                env.update(TaskProxy.event_handler_env)
            ctx = SuiteProcContext(key, cmd, env=env, shell=True)
            try_state = TryState(ctx, conf["handler retry delays"])
            self.event_handler_try_states[key] = try_state
            if try_state.next() is None or try_state.is_delay_done():
                try_state.timeout = None
                SuiteProcPool.get_inst().put_command(
                    ctx, self.event_handler_callback)
            else:
                self.log(
                    INFO,
                    "%s will run after %s (after %s):\n\t%s" % (
                        self.EVENT_HANDLER,
                        try_state.delay_as_seconds(),
                        try_state.timeout_as_str(),
                        ctx.cmd))

    def job_submission_failed(self):
        """Handle job submission failure."""
        self.log(ERROR, 'submission failed')
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "time_submit_exit": get_current_time_string(),
            "submit_status": 1,
        })
        self.submit_method_id = None
        if self.sub_try_state.next() is None:
            # No submission retry lined up: definitive failure.
            flags.pflag = True
            outp = self.identity + " submit-failed"  # hack: see github #476
            self.outputs.add(outp)
            self.outputs.set_completed(outp)
            self.set_status('submit-failed')
            self.handle_event('submission failed', 'job submission failed')
        else:
            # There is a submission retry lined up.
            timeout_str = self.sub_try_state.timeout_as_str()

            delay_msg = "submit-retrying in %s" % (
                self.sub_try_state.delay_as_seconds())
            msg = "submission failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg
            self.summary['waiting for reload'] = self.reconfigure_me

            self.set_status('submit-retrying')
            self._db_events_insert(
                event="submission failed", message=delay_msg)
            self.prerequisites.set_all_satisfied()
            self.outputs.set_all_incomplete()

            # TODO - is this record is redundant with that in handle_event?
            self._db_events_insert(
                event="submission failed",
                message="submit-retrying in " + str(self.sub_try_state.delay))
            self.handle_event(
                "submission retry", "job submission failed, " + delay_msg)
            if self.hold_on_retry:
                self.reset_state_held()

    def job_submission_succeeded(self):
        """Handle job submission succeeded."""
        self.log(INFO, 'submission succeeded')
        if self.tdef.run_mode == 'simulation':
            if self.__class__.stop_sim_mode_job_submission:
                # Real jobs that are ready to run are queued to the proc pool
                # (i.e. the 'ready' state) but not submitted, before shutdown.
                self.set_status('ready')
            else:
                self.started_time = time.time()
                self.summary['started_time'] = self.started_time
                self.summary['started_time_string'] = (
                    get_time_string_from_unix_time(self.started_time))
                self.outputs.set_completed(self.identity + " started")
                self.set_status('running')
            return

        outp = self.identity + ' submitted'
        if not self.outputs.is_completed(outp):
            self.outputs.set_completed(outp)
            # Allow submitted tasks to spawn even if nothing else is happening.
            flags.pflag = True

        self.submitted_time = time.time()

        self.summary['started_time'] = None
        self.summary['started_time_string'] = None
        self.started_time = None
        self.summary['finished_time'] = None
        self.summary['finished_time_string'] = None
        self.finished_time = None

        self.summary['submitted_time'] = self.submitted_time
        self.summary['submitted_time_string'] = (
            get_time_string_from_unix_time(self.submitted_time))
        self.summary['submit_method_id'] = self.submit_method_id
        self.summary['latest_message'] = "submitted"
        self.handle_event(
            'submitted', 'job submitted', db_event='submission succeeded')

        if self.state.is_currently('ready'):
            # The 'started' message can arrive before this. In rare occassions,
            # the submit command of a batch system has sent the job to its
            # server, and the server has started the job before the job submit
            # command returns.
            self.set_status('submitted')
            submit_timeout = self.event_hooks['submission timeout']
            if submit_timeout:
                self.submission_timer_timeout = (
                    self.submitted_time + submit_timeout
                )
            else:
                self.submission_timer_timeout = None
            self.submission_poll_timer.set_timer()

    def job_execution_failed(self):
        """Handle a job failure."""
        self.finished_time = time.time()  # TODO: use time from message
        self.summary['finished_time'] = self.finished_time
        self.summary['finished_time_string'] = (
            get_time_string_from_unix_time(self.finished_time))
        self.db_updates_map[self.TABLE_TASK_JOBS].append({
            "run_status": 1,
            "time_run_exit": self.summary['finished_time_string'],
        })
        self.execution_timer_timeout = None
        if self.run_try_state.next() is None:
            # No retry lined up: definitive failure.
            # Note the 'failed' output is only added if needed.
            flags.pflag = True
            msg = self.identity + ' failed'
            self.outputs.add(msg)
            self.outputs.set_completed(msg)
            self.set_status('failed')
            self.handle_event('failed', 'job failed')

        else:
            # There is a retry lined up
            timeout_str = self.run_try_state.timeout_as_str()
            delay_msg = "retrying in %s" % (
                self.run_try_state.delay_as_seconds())
            msg = "failed, %s (after %s)" % (delay_msg, timeout_str)
            self.log(INFO, "job(%02d) " % self.submit_num + msg)
            self.summary['latest_message'] = msg

            self.set_status('retrying')
            self.prerequisites.set_all_satisfied()
            self.outputs.set_all_incomplete()
            self.handle_event(
                "retry", "job failed, " + delay_msg, db_msg=delay_msg)
            if self.hold_on_retry:
                self.reset_state_held()

    def reset_manual_trigger(self):
        """This is called immediately after manual trigger flag used."""
        if self.manual_trigger:
            self.manual_trigger = False
            self.is_manual_submit = True
            # unset any retry delay timers
            self.run_try_state.timeout = None
            self.sub_try_state.timeout = None

    def set_from_rtconfig(self, cfg=None):
        """Populate task proxy with runtime configuration.

        Some [runtime] config requiring consistency checking on reload,
        and self variables requiring updating for the same.

        """

        if cfg:
            rtconfig = cfg
        else:
            rtconfig = self.tdef.rtconfig

        if not self.retries_configured:
            # configure retry delays before the first try
            self.retries_configured = True
            # TODO - saving the retry delay lists here is not necessary
            # (it can be handled like the polling interval lists).
            if (self.tdef.run_mode == 'live' or
                    (self.tdef.run_mode == 'simulation' and
                        not rtconfig['simulation mode']['disable retries']) or
                    (self.tdef.run_mode == 'dummy' and
                        not rtconfig['dummy mode']['disable retries'])):
                # note that a *copy* of the retry delays list is needed
                # so that all instances of the same task don't pop off
                # the same deque (but copy of rtconfig above solves this).
                self.run_try_state.delays = list(rtconfig['retry delays'])
                self.sub_try_state.delays = list(
                    rtconfig['job submission']['retry delays'])

        rrange = rtconfig['simulation mode']['run time range']
        if len(rrange) != 2:
            raise Exception("ERROR, " + self.tdef.name + ": simulation mode " +
                            "run time range should be ISO 8601-compatible")
        try:
            self.sim_mode_run_length = randrange(rrange[0], rrange[1])
        except Exception, exc:
            traceback.print_exc(exc)
            raise Exception(
                "ERROR: simulation mode task run time range must be [MIN,MAX)")

        self.event_hooks = rtconfig['event hooks']

        self.submission_poll_timer = PollTimer(
            copy(rtconfig['submission polling intervals']),
            copy(GLOBAL_CFG.get(['submission polling intervals'])),
            'submission', self.log)

        self.execution_poll_timer = PollTimer(
            copy(rtconfig['execution polling intervals']),
            copy(GLOBAL_CFG.get(['execution polling intervals'])),
            'execution', self.log)

    def register_job_logs(self, submit_num, result=None):
        """Register job logs in the runtime database."""
        data = []
        if result is None:
            job_log_dir = self.get_job_log_dir(
                self.suite_name, self.tdef.name, self.point, submit_num)
            try:
                for filename in os.listdir(job_log_dir):
                    try:
                        stat = os.stat(os.path.join(job_log_dir, filename))
                    except OSError:
                        continue
                    else:
                        data.append((stat.st_mtime, stat.st_size, filename))
            except OSError:
                pass
        else:
            has_found_delim = False
            for line in result.out.splitlines():
                if has_found_delim:
                    try:
                        mtime, size, filename = line.split("\t")
                    except ValueError:
                        pass
                    else:
                        data.append((mtime, size, filename))
                elif line == "cylc-" + self.JOB_LOGS_RETRIEVE + ":":
                    has_found_delim = True

        rel_job_log_dir = self.get_job_log_dir(
            self.suite_name, self.tdef.name, self.point, submit_num, rel=True)
        for mtime, size, filename in data:
            self.db_inserts_map[self.TABLE_TASK_JOB_LOGS].append({
                "submit_num": submit_num,
                "filename": filename,
                "location": os.path.join(rel_job_log_dir, filename),
                "mtime": mtime,
                "size": size})


    def submit(self, dry_run=False, overrides=None):
        """Submit a job for this task."""

        if self.tdef.run_mode == 'simulation':
            self.job_submission_succeeded()
            return

        if dry_run or not self.job_file_written:
            # Prepare the job submit command and write the job script.
            # In a dry_run, force a rewrite in case of a previous aborted
            # edit-run that left the file write flag set.
            try:
                self._prepare_submit(overrides=overrides)
                JOB_FILE.write(self.job_conf)
                self.job_file_written = True
            except Exception, exc:
                # Could be a bad command template.
                if flags.debug:
                    traceback.print_exc()
                ret_code = 1
                if hasattr(exc, "errno"):
                    ret_code = exc.errno
                self.command_log(SuiteProcContext(
                    self.JOB_SUBMIT, None,
                    err="Failed to construct job submission command",
                    ret_code=1))
                self.command_log(SuiteProcContext(
                    self.JOB_SUBMIT, None, err=exc, ret_code=1))
                self.job_submission_failed()
                return
            if dry_run:
                # Note this is used to bail out in the first stage of an
                # edit-run (i.e. write the job file but don't submit it).
                # In a suite daemon, this must be an edit run.
                self.log(WARNING, "Job file written for an edit-run.")
                return self.job_conf['local job file path']

        # The job file is now (about to be) used: reset the file write flag so
        # that subsequent manual retrigger will generate a new job file.
        self.job_file_written = False
        self.set_status('ready')
        # Send the job to the command pool.
        return self._run_job_command(
            self.JOB_SUBMIT,
            args=[self.job_conf['job file path']],
            callback=self.job_submission_callback,
            is_bg_submit=BATCH_SYS_MANAGER.is_bg_submit(self.batch_sys_name),
            stdin_file_path=self.job_conf['local job file path'])

    def _prepare_submit(self, overrides=None):
        """Get the job submission command.

        Exceptions here are caught in the task pool module.

        """
        self.log(DEBUG, "incrementing submit number")
        self.submit_num += 1
        self.summary['submit_num'] = self.submit_num
        self._db_events_insert(event="incrementing submit number")
        self.job_file_written = False

        local_job_log_dir, common_job_log_path = self._create_job_log_path(
            new_mode=True)
        local_jobfile_path = os.path.join(
            local_job_log_dir, common_job_log_path)

        rtconfig = pdeepcopy(self.tdef.rtconfig)
        poverride(rtconfig, overrides)

        self.set_from_rtconfig(rtconfig)

        # construct the job_sub_method here so that a new one is used if
        # the task is re-triggered by the suite operator - so it will
        # get new stdout/stderr logfiles and not overwrite the old ones.

        # dynamic instantiation - don't know job sub method till run time.
        self.batch_sys_name = rtconfig['job submission']['method']
        self.summary['batch_sys_name'] = self.batch_sys_name

        command = rtconfig['script']
        use_manual = rtconfig['manual completion']
        if self.tdef.run_mode == 'dummy':
            # (dummy tasks don't detach)
            use_manual = False
            command = rtconfig['dummy mode']['script']
            if rtconfig['dummy mode']['disable pre-script']:
                precommand = None
            if rtconfig['dummy mode']['disable post-script']:
                postcommand = None
        else:
            precommand = rtconfig['pre-script']
            postcommand = rtconfig['post-script']

        if self.tdef.suite_polling_cfg:
            # generate automatic suite state polling script
            comstr = "cylc suite-state " + \
                     " --task=" + self.tdef.suite_polling_cfg['task'] + \
                     " --point=" + str(self.point) + \
                     " --status=" + self.tdef.suite_polling_cfg['status']
            if rtconfig['suite state polling']['user']:
                comstr += " --user=" + rtconfig['suite state polling']['user']
            if rtconfig['suite state polling']['host']:
                comstr += " --host=" + rtconfig['suite state polling']['host']
            if rtconfig['suite state polling']['interval']:
                comstr += " --interval=" + str(int(
                    rtconfig['suite state polling']['interval']))
            if rtconfig['suite state polling']['max-polls']:
                comstr += (
                    " --max-polls=" +
                    str(rtconfig['suite state polling']['max-polls']))
            if rtconfig['suite state polling']['run-dir']:
                comstr += (
                    " --run-dir=" +
                    str(rtconfig['suite state polling']['run-dir']))
            comstr += " " + self.tdef.suite_polling_cfg['suite']
            command = "echo " + comstr + "\n" + comstr

        # Determine task host settings now, just before job submission,
        # because dynamic host selection may be used.

        # host may be None (= run task on suite host)
        self.task_host = get_task_host(rtconfig['remote']['host'])
        if self.task_host != "localhost":
            self.log(INFO, "Task host: " + self.task_host)

        self.task_owner = rtconfig['remote']['owner']

        if self.task_owner:
            self.user_at_host = self.task_owner + "@" + self.task_host
        else:
            self.user_at_host = self.task_host
        self.summary['host'] = self.user_at_host
        self.submission_poll_timer.set_host(self.task_host)
        self.execution_poll_timer.set_host(self.task_host)

        RemoteJobHostManager.get_inst().init_suite_run_dir(
            self.suite_name, self.user_at_host)

        self.db_updates_map[self.TABLE_TASK_STATES].append({
            "time_updated": get_current_time_string(),
            "submit_method": self.batch_sys_name,
            "host": self.user_at_host,
            "submit_num": self.submit_num})
        self._populate_job_conf(
            rtconfig, local_jobfile_path, common_job_log_path)
        self.job_conf.update({
            'use manual completion': use_manual,
            'pre-script': precommand,
            'script': command,
            'post-script': postcommand,
        })
        self.db_inserts_map[self.TABLE_TASK_JOBS].append({
            "is_manual_submit": self.is_manual_submit,
            "try_num": self.run_try_state.num,
            "time_submit": get_current_time_string(),
            "user_at_host": self.user_at_host,
            "batch_sys_name": self.batch_sys_name,
        })
        self.is_manual_submit = False

    def _prepare_manip(self):
        """A cut down version of prepare_submit().

        This provides access to job poll commands before the task is submitted,
        for polling in the submitted state or on suite restart.

        """
        if self.user_at_host:
            if "@" in self.user_at_host:
                self.task_owner, self.task_host = (
                    self.user_at_host.split('@', 1))
            else:
                self.task_host = self.user_at_host
        local_job_log_dir, common_job_log_path = self._create_job_log_path()
        local_jobfile_path = os.path.join(
            local_job_log_dir, common_job_log_path)
        rtconfig = pdeepcopy(self.tdef.rtconfig)
        self._populate_job_conf(
            rtconfig, local_jobfile_path, common_job_log_path)

    def _populate_job_conf(
            self, rtconfig, local_jobfile_path, common_job_log_path):
        """Populate the configuration for submitting or manipulating a job."""
        self.batch_sys_name = rtconfig['job submission']['method']
        self.job_conf = {
            'suite name': self.suite_name,
            'task id': self.identity,
            'batch system name': rtconfig['job submission']['method'],
            'directives': rtconfig['directives'],
            'init-script': rtconfig['init-script'],
            'env-script': rtconfig['env-script'],
            'runtime environment': rtconfig['environment'],
            'remote suite path': (
                rtconfig['remote']['suite definition directory']),
            'job script shell': rtconfig['job submission']['shell'],
            'batch submit command template': (
                rtconfig['job submission']['command template']),
            'work sub-directory': rtconfig['work sub-directory'],
            'use manual completion': False,
            'pre-script': '',
            'script': '',
            'post-script': '',
            'namespace hierarchy': self.tdef.namespace_hierarchy,
            'submission try number': self.sub_try_state.num,
            'try number': self.run_try_state.num,
            'absolute submit number': self.submit_num,
            'is cold-start': self.tdef.is_coldstart,
            'owner': self.task_owner,
            'host': self.task_host,
            'log files': self.logfiles,
            'common job log path': common_job_log_path,
            'local job file path': local_jobfile_path,
            'job file path': local_jobfile_path,
        }

        log_files = self.job_conf['log files']
        log_files.add_path(local_jobfile_path)

        if not self.job_conf['host']:
            self.job_conf['host'] = socket.gethostname()

        if (is_remote_host(self.job_conf['host']) or
                is_remote_user(self.job_conf['owner'])):
            remote_job_log_dir = GLOBAL_CFG.get_derived_host_item(
                self.suite_name,
                'suite job log directory',
                self.task_host,
                self.task_owner)

            remote_path = os.path.join(
                remote_job_log_dir, self.job_conf['common job log path'])

            # Used in command construction:
            self.job_conf['job file path'] = remote_path

            # Record paths of remote log files for access by gui
            # N.B. Need to consider remote log files in shared file system
            #      accessible from the suite daemon, mounted under the same
            #      path or otherwise.
            prefix = self.job_conf['host'] + ':' + remote_path
            if self.job_conf['owner']:
                prefix = self.job_conf['owner'] + "@" + prefix
            log_files.add_path(prefix + '.out')
            log_files.add_path(prefix + '.err')
        else:
            # interpolate environment variables in extra logs
            for idx in range(len(log_files.paths)):
                log_files.paths[idx] = expandvars(log_files.paths[idx])

            # Record paths of local log files for access by gui
            log_files.add_path(self.job_conf['job file path'] + '.out')
            log_files.add_path(self.job_conf['job file path'] + '.err')

    def check_timers(self):
        """Check submission and execution timeout timers.

        Not called in simulation mode.

        """
        if self.state.is_currently('submitted'):
            self.check_submission_timeout()
            if self.submission_poll_timer:
                if self.submission_poll_timer.get():
                    self.poll()
                    self.submission_poll_timer.set_timer()
        elif self.state.is_currently('running'):
            self.check_execution_timeout()
            if self.execution_poll_timer:
                if self.execution_poll_timer.get():
                    self.poll()
                    self.execution_poll_timer.set_timer()

    def check_submission_timeout(self):
        """Check submission timeout, only called if in "submitted" state."""
        if self.submission_timer_timeout is None:
            # (explicit None in case of a zero timeout!)
            # no timer set
            return

        # if timed out, log warning, poll, queue event handler, and turn off
        # the timer
        if time.time() > self.submission_timer_timeout:
            msg = 'job submitted %s ago, but has not started' % (
                get_seconds_as_interval_string(
                    self.event_hooks['submission timeout'])
            )
            self.log(WARNING, msg)
            self.poll()
            self.handle_event('submission timeout', msg)
            self.submission_timer_timeout = None

    def check_execution_timeout(self):
        """Check execution timeout, only called if in "running" state."""
        if self.execution_timer_timeout is None:
            # (explicit None in case of a zero timeout!)
            # no timer set
            return

        # if timed out: log warning, poll, queue event handler, and turn off
        # the timer
        if time.time() > self.execution_timer_timeout:
            if self.event_hooks['reset timer']:
                # the timer is being re-started by put messages
                msg = 'last message %s ago, but job not finished'
            else:
                msg = 'job started %s ago, but has not finished'
            msg = msg % get_seconds_as_interval_string(
                self.event_hooks['execution timeout'])
            self.log(WARNING, msg)
            self.poll()
            self.handle_event('execution timeout', msg)
            self.execution_timer_timeout = None

    def sim_time_check(self):
        """Check simulation time."""
        timeout = self.started_time + self.sim_mode_run_length
        if time.time() > timeout:
            if self.tdef.rtconfig['simulation mode']['simulate failure']:
                self.message_queue.put('NORMAL', self.identity + ' submitted')
                self.message_queue.put('CRITICAL', self.identity + ' failed')
            else:
                self.message_queue.put('NORMAL', self.identity + ' submitted')
                self.message_queue.put('NORMAL', self.identity + ' succeeded')
            return True
        else:
            return False

    def reject_if_failed(self, message):
        """Reject a message if in the failed state.

        Handle 'enable resurrection' mode.

        """
        if self.state.is_currently('failed'):
            if self.tdef.rtconfig['enable resurrection']:
                self.log(
                    WARNING,
                    'message receive while failed:' +
                    ' I am returning from the dead!'
                )
                return False
            else:
                self.log(
                    WARNING,
                    'rejecting a message received while in the failed state:'
                )
                self.log(WARNING, '  ' + message)
            return True
        else:
            return False

    def process_incoming_messages(self):
        """Handle incoming messages."""
        queue = self.message_queue.get_queue()
        while queue.qsize() > 0:
            try:
                self.process_incoming_message(queue.get(block=False))
            except Queue.Empty:
                break
            queue.task_done()

    def process_incoming_message(self, (priority, message)):
        """Parse an incoming task message and update task state.

        Correctly handle late (out of order) message which would otherwise set
        the state backward in the natural order of events.

        """
        # TODO - formalize state ordering, for: 'if new_state < old_state'

        # Log incoming messages with '>' to distinguish non-message log entries
        self.log(
            self.LOGGING_LVL_OF.get(priority, INFO),
            '(current:' + self.state.get_status() + ')> ' + message)
        # always update the suite state summary for latest message
        self.summary['latest_message'] = message.replace(
            self.identity, "", 1).strip()
        flags.iflag = True

        if self.reject_if_failed(message):
            # Failed tasks do not send messages unless declared resurrectable
            return

        msg_was_polled = False
        if message.startswith('polled '):
            if not self.state.is_currently('submitted', 'running'):
                # Polling can take a few seconds or more, so it is
                # possible for a poll result to come in after a task
                # finishes normally (success or failure) - in which case
                # we should ignore the poll result.
                self.log(
                    WARNING,
                    "Ignoring late poll result: task is not active")
                return
            # remove polling prefix and treat as a normal task message
            msg_was_polled = True
            message = message[7:]

        # remove the remote event time (or "unknown-time" from polling) from
        # the end:
        message = self.POLL_SUFFIX_RE.sub('', message)

        # Remove the prepended task ID.
        content = message.replace(self.identity + ' ', '')

        # If the message matches a registered output, record it as completed.
        if self.outputs.exists(message):
            if not self.outputs.is_completed(message):
                flags.pflag = True
                self.outputs.set_completed(message)
                self._db_events_insert(
                    event="output completed", message=content)
            elif content == 'started' and self.job_vacated:
                self.job_vacated = False
                self.log(WARNING, "Vacated job restarted: " + message)
            elif not msg_was_polled:
                # This output has already been reported complete. Not an error
                # condition - maybe the network was down for a bit. Ok for
                # polling as multiple polls *should* produce the same result.
                self.log(
                    WARNING,
                    "Unexpected output (already completed):\n  " + message)

        if priority == TaskMessage.WARNING:
            self.handle_event('warning', content, db_update=False)

        if self.event_hooks['reset timer']:
            # Reset execution timer on incoming messages
            execution_timeout = self.event_hooks['execution timeout']
            if execution_timeout:
                self.execution_timer_timeout = (
                    time.time() + execution_timeout
                )

        elif (content == TaskMessage.STARTED and
                self.state.is_currently(
                    'ready', 'submitted', 'submit-failed')):
            # Received a 'task started' message
            flags.pflag = True
            self.set_status('running')
            self.started_time = time.time()  # TODO: use time from message
            self.summary['started_time'] = self.started_time
            self.summary['started_time_string'] = (
                get_time_string_from_unix_time(self.started_time))
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "time_run": self.summary['started_time_string']})
            execution_timeout = self.event_hooks['execution timeout']
            if execution_timeout:
                self.execution_timer_timeout = (
                    self.started_time + execution_timeout
                )
            else:
                self.execution_timer_timeout = None

            # submission was successful so reset submission try number
            self.sub_try_state.num = 1
            self.handle_event('started', 'job started')
            self.execution_poll_timer.set_timer()

        elif (content == TaskMessage.SUCCEEDED and
                self.state.is_currently(
                    'ready', 'submitted', 'submit-failed', 'running',
                    'failed')):
            # Received a 'task succeeded' message
            # (submit* states in case of very fast submission and execution)
            self.execution_timer_timeout = None
            self.hold_on_retry = False
            flags.pflag = True
            self.finished_time = time.time()
            self.summary['finished_time'] = self.finished_time
            self.summary['finished_time_string'] = (
                get_time_string_from_unix_time(self.finished_time))
            self.db_updates_map[self.TABLE_TASK_JOBS].append({
                "run_status": 0,
                "time_run_exit": self.summary['finished_time_string'],
            })
            # Update mean elapsed time only on task succeeded.
            self.tdef.update_mean_total_elapsed_time(
                self.started_time, self.finished_time)
            self.set_status('succeeded')
            self.handle_event("succeeded", "job succeeded")
            if not self.outputs.all_completed():
                # In case start or succeed before submitted message.
                msg = "Assuming non-reported outputs were completed:"
                for key in self.outputs.not_completed:
                    msg += "\n" + key
                self.log(INFO, msg)
                self.outputs.set_all_completed()

        elif (content == TaskMessage.FAILED and
                self.state.is_currently(
                    'ready', 'submitted', 'submit-failed', 'running')):
            # (submit- states in case of very fast submission and execution).
            self.job_execution_failed()

        elif content.startswith(TaskMessage.FAIL_MESSAGE_PREFIX):
            # capture and record signals sent to task proxy
            self._db_events_insert(event="signaled", message=content)
            signal = content.replace(TaskMessage.FAIL_MESSAGE_PREFIX, "")
            self.db_updates_map[self.TABLE_TASK_JOBS].append(
                {"run_signal": signal})

        elif content.startswith(TaskMessage.VACATION_MESSAGE_PREFIX):
            flags.pflag = True
            self.set_status('submitted')
            self._db_events_insert(event="vacated", message=content)
            self.execution_timer_timeout = None
            # TODO - check summary item value compat with GUI:
            self.summary['started_time'] = None
            self.summary['started_time_string'] = None
            self.sub_try_state.num = 1
            self.job_vacated = True

        elif content == "submission failed":
            # This can arrive via a poll.
            outp = self.identity + ' submitted'
            if self.outputs.is_completed(outp):
                self.outputs.remove(outp)
            self.submission_timer_timeout = None
            self.job_submission_failed()

        else:
            # Unhandled messages. These include:
            #  * general non-output/progress messages
            #  * poll messages that repeat previous results
            # Note that all messages are logged already at the top.
            self.log(DEBUG, '(current: %s) unhandled: %s' % (
                self.state.get_status(), content))

    def process_event_handler_retries(self):
        """Run delayed event handlers or retry failed ones."""
        for key, try_state in self.event_handler_try_states.items():
            if try_state.ctx and try_state.is_delay_done():
                try_state.timeout = None
                ctx = SuiteProcContext(
                    try_state.ctx.cmd_type,
                    try_state.ctx.cmd,
                    **try_state.ctx.cmd_kwargs)
                try_state.ctx = ctx
                SuiteProcPool.get_inst().put_command(
                    ctx, self.event_handler_callback)

    def set_status(self, status):
        """Set, log and record task status."""
        if status != self.state.get_status():
            flags.iflag = True
            self.log(DEBUG, '(setting:' + status + ')')
            self.state.set_status(status)
            self.db_updates_map[self.TABLE_TASK_STATES].append({
                "time_updated": get_current_time_string(),
                "submit_num": self.submit_num,
                "try_num": self.run_try_state.num,
                "status": status
            })

    def dump_state(self, handle):
        """Write state information to the state dump file."""
        handle.write(self.identity + ' : ' + self.state.dump() + '\n')

    def spawn(self, state):
        """Spawn the successor of this task proxy."""
        self.state.set_spawned()
        next_point = self.next_point()
        if next_point:
            return TaskProxy(self.tdef, next_point, state, self.stop_point)
        else:
            # next_point instance is out of the sequence bounds
            return None

    def ready_to_spawn(self):
        """Spawn on submission.

        Prevents uncontrolled spawning but allows successive instances to run
        in parallel.

        A task can only fail after first being submitted, therefore a failed
        task should spawn if it hasn't already. Resetting a waiting task to
        failed will result in it spawning.

        """
        if self.tdef.is_coldstart:
            self.state.set_spawned()
        return not self.state.has_spawned() and self.state.is_currently(
            'expired', 'submitted', 'running', 'succeeded', 'failed',
            'retrying')

    def done(self):
        """Return True if task has succeeded and spawned."""
        return (
            self.state.is_currently('succeeded') and self.state.has_spawned())

    def get_state_summary(self):
        """Return a dict containing the state summary of this task proxy."""
        self.summary['state'] = self.state.get_status()
        self.summary['spawned'] = self.state.has_spawned()
        self.summary['mean total elapsed time'] = (
            self.tdef.mean_total_elapsed_time)
        return self.summary

    def not_fully_satisfied(self):
        """Return True if prerequisites are not fully satisfied."""
        return (not self.prerequisites.all_satisfied() or
                not self.suicide_prerequisites.all_satisfied())

    def satisfy_me(self, task_outputs):
        """Attempt to to satify the prerequisites of this task proxy."""
        self.prerequisites.satisfy_me(task_outputs)
        if self.suicide_prerequisites.count() > 0:
            self.suicide_prerequisites.satisfy_me(task_outputs)

    def next_point(self):
        """Return the next cycle point."""
        p_next = None
        adjusted = []
        for seq in self.tdef.sequences:
            nxt = seq.get_next_point(self.point)
            if nxt:
                # may be None if beyond the sequence bounds
                adjusted.append(nxt)
        if adjusted:
            p_next = min(adjusted)
        return p_next

    def poll(self):
        """Poll my live task job and update status accordingly."""
        return self._manip_job_status(
            self.JOB_POLL, self.job_poll_callback)

    def kill(self):
        """Kill current job of this task."""
        self.reset_state_held()
        return self._manip_job_status(
            self.JOB_KILL,
            self.job_kill_callback, ['running', 'submitted'])
 
    def _create_job_log_path(self, new_mode=False):
        """Return a new job log path on the suite host, in two parts.

        /part1/part2

        * part1: the top level job log directory on the suite host.
        * part2: the rest, which is also used on remote task hosts.

        The full local job log directory is created if necessary, and its
        parent symlinked to NN (submit number).

        """

        suite_job_log_dir = GLOBAL_CFG.get_derived_host_item(
            self.suite_name, "suite job log directory")

        the_rest_dir = os.path.join(
            str(self.point), self.tdef.name, "%02d" % int(self.submit_num))
        the_rest = os.path.join(the_rest_dir, "job")

        local_log_dir = os.path.join(suite_job_log_dir, the_rest_dir)

        if new_mode:
            try:
                rmtree(local_log_dir)
            except OSError:
                pass

        mkdir_p(local_log_dir)
        target = os.path.join(os.path.dirname(local_log_dir), "NN")
        try:
            os.unlink(target)
        except OSError:
            pass
        try:
            os.symlink(os.path.basename(local_log_dir), target)
        except OSError as exc:
            if not exc.filename:
                exc.filename = target
            raise exc
        return suite_job_log_dir, the_rest

    def _manip_job_status(self, cmd_key, callback, ok_states=None):
        """Manipulate the job status, e.g. poll or kill."""
        # No real jobs in simulation mode.
        if self.tdef.run_mode == 'simulation':
            if cmd_key == self.JOB_KILL:
                self.reset_state_failed()
            return
        # Check that task states are compatible with the manipulation
        if ok_states and not self.state.is_currently(*ok_states):
            self.log(
                WARNING,
                'Can only do %s when in %s states' % (cmd_key, str(ok_states)))
            return
        # Detached tasks
        if self.tdef.rtconfig['manual completion']:
            self.log(
                WARNING,
                "Cannot %s detaching tasks (job ID unknown)" % (cmd_key))
            return

        # Ensure settings are ready for manipulation on suite restart, etc
        if self.job_conf is None:
            self._prepare_manip()

        # Invoke the manipulation
        return self._run_job_command(
            cmd_key,
            args=[self.job_conf["job file path"] + ".status"],
            callback=callback)

    def _run_job_command(
            self, cmd_key, args, callback, is_bg_submit=None,
            stdin_file_path=None):
        """Run a job command, e.g. submit, poll, kill, etc.

        Run a job command with the multiprocess pool.

        """
        if self.user_at_host in [user + '@localhost', 'localhost']:
            cmd = ["cylc", cmd_key] + list(args)
        else:  # if it is a remote job
            ssh_tmpl = GLOBAL_CFG.get_host_item(
                'remote shell template',
                self.task_host,
                self.task_owner).replace(" %s", "")
            r_cylc = GLOBAL_CFG.get_host_item(
                'cylc executable', self.task_host, self.task_owner)
            sh_tmpl = "CYLC_VERSION='%s' "
            if GLOBAL_CFG.get_host_item(
                    'use login shell', self.task_host, self.task_owner):
                sh_tmpl += "bash -lc 'exec \"$0\" \"$@\"' \"%s\" '%s'"
            else:
                sh_tmpl += "\"%s\" '%s'"
            sh_cmd = sh_tmpl % (os.environ['CYLC_VERSION'], r_cylc, cmd_key)
            if stdin_file_path:
                sh_cmd += " --remote-mode"
            for arg in args:
                sh_cmd += ' "%s"' % (arg)
            cmd = shlex.split(ssh_tmpl) + [str(self.user_at_host), sh_cmd]

        # Queue the command for execution
        self.log(INFO, "job(%02d) initiate %s" % (self.submit_num, cmd_key))
        ctx = SuiteProcContext(
            cmd_key, cmd, is_bg_submit=is_bg_submit,
            stdin_file_path=stdin_file_path)
        return SuiteProcPool.get_inst().put_command(ctx, callback)
