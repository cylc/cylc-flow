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
"""Retrieve information about the running or stopped suite for cylc gui."""

import re
import sys
import atexit
import gobject
import threading
from time import sleep, time
import traceback

import cylc.flags
from cylc.dump import get_stop_state_summary
from cylc.gui.cat_state import cat_state
from cylc.gui.warning_dialog import warning_dialog
from cylc.network.client import (
    SuiteRuntimeServiceClient, ClientError, ClientDeniedError)
from cylc.suite_status import (
    SUITE_STATUS_NOT_CONNECTED, SUITE_STATUS_CONNECTED,
    SUITE_STATUS_INITIALISING, SUITE_STATUS_STOPPED, SUITE_STATUS_STOPPING
)
from cylc.task_id import TaskID
from cylc.task_state import TASK_STATUSES_RESTRICTED
from cylc.version import CYLC_VERSION
from cylc.wallclock import (
    get_current_time_string,
    get_seconds_as_interval_string,
    get_time_string_from_unix_time
)


class ConnectSchd(object):
    """Keep information on whether the updater should poll or not.

    Attributes:
    .t_init - start time
    .t_prev - previous poll time
    .dt_next - estimated duration before the next poll
    """

    DELAYS = {
        (None, 5.0): 1.0,
        (5.0, 60.0): 5.0,
        (60.0, 300.0): 60.0,
        (300.0, None): 300.0}

    def __init__(self, start=False):
        """Return a new instance.

        If start is False, the updater can always poll.

        If start is True, the updater should only poll if the ready method
        returns True.

        """

        self.t_init = None
        self.t_prev = None
        self.dt_next = 0.0
        if start:
            self.start()

    def ready(self):
        """Return True if a poll is ready."""
        self.dt_next = 0.0
        if self.t_init is None:
            return True
        if self.t_prev is None:
            self.t_prev = time()
            return True
        dt_init = time() - self.t_init
        dt_prev = time() - self.t_prev
        for key, delay in self.DELAYS.items():
            lower, upper = key
            if ((lower is None or dt_init >= lower) and
                    (upper is None or dt_init < upper)):
                if dt_prev > delay:
                    self.t_prev = time()
                    return True
                else:
                    self.dt_next = round(delay - dt_prev, 2)
                    if cylc.flags.debug:
                        print >> sys.stderr, (
                            '  ConnectSchd not ready, next poll in PT%sS' %
                            self.dt_next)
                    return False
        return True

    def start(self):
        """Start keeping track of latest poll, if not already started."""
        if self.t_init is None:
            if cylc.flags.debug:
                print >> sys.stderr, '  ConnectSchd start'
            self.t_init = time()
            self.t_prev = None

    def stop(self):
        """Stop keeping track of latest poll."""
        if self.t_init is not None or self.t_prev is not None:
            if cylc.flags.debug:
                print >> sys.stderr, '  ConnectSchd stop'
        self.t_init = None
        self.t_prev = None


class Updater(threading.Thread):

    """Retrieve information about the running or stopped suite."""

    def __init__(self, app):

        super(Updater, self).__init__()

        self.quit = False

        self.app_window = app.window
        self.cfg = app.cfg
        self.info_bar = app.info_bar

        self.summary_update_time = None
        self.err_update_time = None
        self.err_log_lines = []
        self._err_num_log_lines = 10
        self.err_log_size = 0
        self.task_list = []

        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.all_families = {}
        self.global_summary = {}

        self.daemon_version = None

        self.stop_summary = None
        self.ancestors = {}
        self.ancestors_pruned = {}
        self.descendants = {}
        self.mode = "waiting..."
        self.update_time_str = "waiting..."
        self.status = SUITE_STATUS_NOT_CONNECTED
        self.is_reloading = False
        self.connected = False
        self._no_update_event = threading.Event()
        self.connect_schd = ConnectSchd()
        self.last_update_time = time()
        self.ns_defn_order = []
        self.dict_ns_defn_order = {}
        self.restricted_display = app.restricted_display
        self.filter_name_string = ''
        self.filter_states_excl = []
        self.kept_task_ids = set()
        self.filt_task_ids = set()

        self.connect_fail_warned = False
        self.version_mismatch_warned = False

        self.client = SuiteRuntimeServiceClient(
            self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port,
            self.cfg.comms_timeout, self.cfg.my_uuid)
        # Report sign-out on exit.
        atexit.register(self.client.signout)

    def reconnect(self):
        """Try to reconnect to the suite daemon."""
        if cylc.flags.debug:
            print >> sys.stderr, "  reconnection...",
        try:
            self.daemon_version = self.client.get_info('get_cylc_version')
        except ClientDeniedError as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            if not self.connect_fail_warned:
                self.connect_fail_warned = True
                gobject.idle_add(
                    self.warn,
                    "ERROR: %s\n\nIncorrect suite passphrase?" % exc)
            return
        except ClientError as exc:
            # Failed to (re)connect
            # Suite not running, starting up or just stopped.
            if cylc.flags.debug:
                traceback.print_exc()
            # Use info bar to display stop summary if available.
            # Otherwise, just display the reconnect count down.
            if self.cfg.suite and self.stop_summary is None:
                stop_summary = get_stop_state_summary(
                    cat_state(self.cfg.suite, self.cfg.host, self.cfg.owner))
                self.last_update_time = time()
                if stop_summary != self.stop_summary:
                    self.stop_summary = stop_summary
                    self.status = SUITE_STATUS_STOPPED
                    gobject.idle_add(
                        self.info_bar.set_stop_summary, stop_summary)
            try:
                update_time_str = get_time_string_from_unix_time(
                    self.stop_summary[0]["last_updated"])
            except (AttributeError, IndexError, KeyError, TypeError):
                update_time_str = None
            gobject.idle_add(
                self.info_bar.set_update_time,
                update_time_str, self.info_bar.DISCONNECTED_TEXT)
            return
        except Exception as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            if not self.connect_fail_warned:
                self.connect_fail_warned = True
                gobject.idle_add(self.warn, str(exc))
            return

        gobject.idle_add(
            self.app_window.set_title, "%s - %s:%s" % (
                self.cfg.suite, self.client.host, self.client.port))
        if cylc.flags.debug:
            print >> sys.stderr, "succeeded"
        # Connected.
        self.connected = True
        # This status will be very transient:
        self.set_status(SUITE_STATUS_CONNECTED)
        self.connect_fail_warned = False

        self.connect_schd.stop()
        if cylc.flags.debug:
            print >> sys.stderr, (
                "succeeded: daemon v %s" % self.daemon_version)
        if (self.daemon_version != CYLC_VERSION and
                not self.version_mismatch_warned):
            # (warn only once - reconnect() will be called multiple times
            # during initialisation of daemons at <= 6.4.0 (for which the state
            # summary object is not connected until all tasks are loaded).
            gobject.idle_add(
                self.warn,
                "Warning: cylc version mismatch!\n\n" +
                "Suite running with %r.\n" % self.daemon_version +
                "gcylc at %r.\n" % CYLC_VERSION)
            self.version_mismatch_warned = True
        self.stop_summary = None
        self.err_log_lines = []
        self.err_log_size = 0
        self.last_update_time = time()

    def set_update(self, should_update):
        """Set update flag."""
        if should_update:
            self._no_update_event.clear()
        else:
            self._no_update_event.set()

    def retrieve_err_log(self):
        """Retrieve suite err log; return True if it has changed."""
        new_err_content, new_err_size = (
            self.client.get_err_content(
                self.err_log_size, self._err_num_log_lines)
        )
        err_log_changed = (new_err_size != self.err_log_size)
        if err_log_changed:
            self.err_log_lines += new_err_content.splitlines()
            self.err_log_lines = self.err_log_lines[-self._err_num_log_lines:]
            self.err_log_size = new_err_size
        return err_log_changed

    def get_update_times(self):
        """Retrieve suite summary update time; return True if changed."""
        prev_summary_update_time = self.summary_update_time
        prev_err_update_time = self.err_update_time
        self.summary_update_time, self.err_update_time = (
            self.client.get_update_times())
        if self.summary_update_time is None:
            self.set_status(SUITE_STATUS_INITIALISING)
        else:
            self.summary_update_time = float(self.summary_update_time)
        if self.err_update_time is not None:
            self.err_update_time = float(self.err_update_time)
        return (
            prev_summary_update_time != self.summary_update_time,
            prev_err_update_time != self.err_update_time)

    def retrieve_state_summaries(self):
        """Retrieve suite summary."""
        glbl, states, fam_states = self.client.get_suite_state_summary()

        (self.ancestors, self.ancestors_pruned, self.descendants,
            self.all_families) = self.client.get_info(
                {'function': 'get_first_parent_ancestors'},
                {'function': 'get_first_parent_ancestors', 'pruned': True},
                {'function': 'get_first_parent_descendants'},
                {'function': 'get_all_families'})

        self.mode = glbl['run_mode']

        if self.cfg.use_defn_order:
            nsdo = glbl['namespace definition order']
            if self.ns_defn_order != nsdo:
                self.ns_defn_order = nsdo
                self.dict_ns_defn_order = dict(zip(nsdo, range(0, len(nsdo))))

        self.update_time_str = get_time_string_from_unix_time(
            glbl['last_updated'])
        self.global_summary = glbl

        if self.restricted_display:
            states = self.filter_for_restricted_display(states)

        self.full_state_summary = states
        self.full_fam_state_summary = fam_states
        self.refilter()

        self.status = glbl['status_string']
        self.is_reloading = glbl['reloading']

    def set_stopped(self):
        """Reset data and clients when suite is stopped."""
        self.connected = False
        self.set_status(SUITE_STATUS_STOPPED)
        self.connect_schd.start()
        self.summary_update_time = None
        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.all_families = {}
        self.global_summary = {}
        self.cfg.port = None
        if self.cfg.host is None:
            self.client.host = None
        self.client.port = None

        if self.cfg.host:
            gobject.idle_add(
                self.app_window.set_title, "%s - %s" % (
                    self.cfg.suite, self.cfg.host))
        else:
            gobject.idle_add(
                self.app_window.set_title, str(self.cfg.suite))

    def set_status(self, status=None):
        """Update status bar."""
        if status == self.status:
            return
        if status is not None:
            self.status = status
        gobject.idle_add(self.info_bar.set_status, self.status)

    def warn(self, msg):
        """Pop up a warning dialog; call on idle_add!"""
        warning_dialog(msg, self.info_bar.get_toplevel()).warn()
        return False

    def update(self):
        """Try and connect and do an update."""
        if self._no_update_event.is_set():
            return False
        if not self.connect_schd.ready():
            self.info_bar.set_update_time(
                None,
                get_seconds_as_interval_string(
                    round(self.connect_schd.dt_next)))
            return False
        if cylc.flags.debug:
            print >> sys.stderr, "UPDATE %s" % get_current_time_string()
        if not self.connected:
            # Only reconnect via self.reconnect().
            self.reconnect()
        if not self.connected:
            self.set_stopped()
            if cylc.flags.debug:
                print >> sys.stderr, "(not connected)"
            return False
        if cylc.flags.debug:
            print >> sys.stderr, "(connected)"
        try:
            summaries_changed, err_log_changed = self.get_update_times()
            if self.summary_update_time is not None and summaries_changed:
                self.retrieve_state_summaries()
            if self.err_update_time is not None and err_log_changed:
                self.retrieve_err_log()
        except Exception as exc:
            if self.status == SUITE_STATUS_STOPPING:
                # Expected stop: prevent the reconnection warning dialog.
                self.connect_fail_warned = True
            if cylc.flags.debug:
                print >> sys.stderr, "  CONNECTION LOST", str(exc)
            self.set_stopped()
            if self.info_bar.prog_bar_active():
                gobject.idle_add(self.info_bar.prog_bar_stop)
            self.reconnect()
            return False
        else:
            # Got suite data.
            self.version_mismatch_warned = False
            status_str = None
            if self.status in [SUITE_STATUS_INITIALISING,
                               SUITE_STATUS_STOPPING]:
                status_str = self.status
            elif self.is_reloading:
                status_str = "reloading"
            if status_str is None:
                gobject.idle_add(self.info_bar.prog_bar_stop)
            elif self.info_bar.prog_bar_can_start():
                gobject.idle_add(self.info_bar.prog_bar_start, status_str)
            return summaries_changed or err_log_changed

    def filter_by_name(self, states):
        """Filter by name string."""
        return dict(
            (i, j) for i, j in states.items() if
            self.filter_name_string in j['name'] or
            re.search(self.filter_name_string, j['name']))

    def filter_by_state(self, states):
        """Filter by state key."""
        return dict(
            (i, j) for i, j in states.items() if
            j['state'] not in self.filter_states_excl)

    def filter_families(self, families):
        """Remove family summaries if no members are present."""
        # TODO - IS THERE ANY NEED TO DO THIS?
        fam_states = {}
        for fam_id, summary in families.items():
            name, point_string = TaskID.split(fam_id)
            remove = True
            for mem in self.descendants[name]:
                mem_id = TaskID.get(mem, point_string)
                if mem_id in self.state_summary:
                    remove = False
                    break
            if not remove:
                fam_states[fam_id] = summary
        return fam_states

    @classmethod
    def filter_for_restricted_display(cls, states):
        """Filter for legal restricted states."""
        return dict((i, j) for i, j in states.items() if
                    j['state'] in TASK_STATUSES_RESTRICTED)

    def refilter(self):
        """filter from the full state summary"""
        if self.filter_name_string or self.filter_states_excl:
            states = self.full_state_summary
            all_ids = set(states.keys())
            if self.filter_name_string:
                states = self.filter_by_name(states)
            if self.filter_states_excl:
                states = self.filter_by_state(states)
            self.state_summary = states
            fam_states = self.full_fam_state_summary
            self.fam_state_summary = self.filter_families(fam_states)
            self.kept_task_ids = set(states.keys())
            self.filt_task_ids = all_ids - self.kept_task_ids
        else:
            self.state_summary = self.full_state_summary
            self.fam_state_summary = self.full_fam_state_summary
            self.filt_task_ids = set()
            self.kept_task_ids = set(self.state_summary.keys())
        self.task_list = list(
            set([t['name'] for t in self.state_summary.values()]))
        self.task_list.sort()

    def update_globals(self):
        """Update common widgets."""
        self.info_bar.set_state(self.global_summary.get("states", []))
        self.info_bar.set_mode(self.mode)
        self.info_bar.set_update_time(self.update_time_str)
        self.info_bar.set_status(self.status)
        self.info_bar.set_log("\n".join(self.err_log_lines), self.err_log_size)
        return False

    def stop(self):
        """Tell self.run to exit."""
        self.quit = True

    def run(self):
        """Start the thread."""
        while not self.quit:
            if self.update():
                self.last_update_time = time()
                gobject.idle_add(self.update_globals)
            sleep(1)

    @staticmethod
    def get_id_summary(
            id_, task_state_summary, fam_state_summary, id_family_map):
        """Return some state information about a task or family id."""
        prefix_text = ""
        meta_text = ""
        sub_text = ""
        sub_states = {}
        stack = [(id_, 0)]
        done_ids = []
        for summary in [task_state_summary, fam_state_summary]:
            if id_ in summary:
                title = summary[id_].get('title')
                if title:
                    meta_text += "\n" + title.strip()
                description = summary[id_].get('description')
                if description:
                    meta_text += "\n" + description.strip()
        while stack:
            this_id, depth = stack.pop(0)
            if this_id in done_ids:  # family dive down will give duplicates
                continue
            done_ids.append(this_id)
            prefix = "\n" + " " * 4 * depth + this_id
            if this_id in task_state_summary:
                submit_num = task_state_summary[this_id].get('submit_num')
                if submit_num:
                    prefix += "(%02d)" % submit_num
                state = task_state_summary[this_id]['state']
                sub_text += prefix + " " + state
                sub_states.setdefault(state, 0)
                sub_states[state] += 1
            elif this_id in fam_state_summary:
                name, point_string = TaskID.split(this_id)
                sub_text += prefix + " " + fam_state_summary[this_id]['state']
                for child in reversed(sorted(id_family_map[name])):
                    child_id = TaskID.get(child, point_string)
                    stack.insert(0, (child_id, depth + 1))
            if not prefix_text:
                prefix_text = sub_text.strip()
                sub_text = ""
        if len(sub_text.splitlines()) > 10:
            state_items = sub_states.items()
            state_items.sort()
            state_items.sort(lambda x, y: cmp(y[1], x[1]))
            sub_text = ""
            for state, number in state_items:
                sub_text += "\n    {0} tasks {1}".format(number, state)
        if sub_text and meta_text:
            sub_text = "\n" + sub_text
        text = prefix_text + meta_text + sub_text
        if not text:
            return id_
        return text
