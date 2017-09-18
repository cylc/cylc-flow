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

import atexit
import gobject
import re
import sys
import threading
from time import sleep, time
import traceback

import cylc.flags
from cylc.dump import get_stop_state_summary
from cylc.gui.cat_state import cat_state
from cylc.gui.warning_dialog import warning_dialog
from cylc.network.httpclient import SuiteRuntimeServiceClient, ClientError
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

    # Maximum and minute update durations (in seconds) for a running suite
    MAX_UPDATE_DURATION = 15.0

    def __init__(self, app):

        super(Updater, self).__init__()

        self.quit = False

        self.app_window = app.window
        self.cfg = app.cfg
        self.info_bar = app.info_bar
        self.full_mode = True

        self.err_log_lines = []
        self.task_list = []

        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.all_families = {}
        self.global_summary = {}
        self.ancestors = {}
        self.ancestors_pruned = {}
        self.descendants = {}
        self.stop_summary = None

        self.mode = "waiting..."
        self.update_time_str = "waiting..."
        self.last_update_time = time()
        self.next_update_time = self.last_update_time
        self.status = SUITE_STATUS_NOT_CONNECTED
        self.is_reloading = False
        self.connected = False
        self.no_update_event = threading.Event()
        self.connect_schd = ConnectSchd()
        self.ns_defn_order = []
        self.dict_ns_defn_order = {}
        self.restricted_display = app.restricted_display
        self.filter_name_string = ''
        self.filter_states_excl = []
        self.kept_task_ids = set()
        self.filt_task_ids = set()

        self.version_mismatch_warned = False

        self.client = SuiteRuntimeServiceClient(
            self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port,
            self.cfg.comms_timeout, self.cfg.my_uuid)
        # Report sign-out on exit.
        atexit.register(self.signout)

    def signout(self):
        """Sign out the client, if possible."""
        try:
            self.client.signout()
        except ClientError:
            pass

    def set_stopped(self):
        """Reset data and clients when suite is stopped."""
        if cylc.flags.debug:
            sys.stderr.write("%s NOT CONNECTED\n" % get_current_time_string())
        self.full_mode = True
        self.connected = False
        self.set_status(SUITE_STATUS_STOPPED)
        self.connect_schd.start()
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
                self.app_window.set_title,
                "%s - %s" % (self.cfg.suite, self.cfg.host))
        else:
            gobject.idle_add(
                self.app_window.set_title, str(self.cfg.suite))

        # Use info bar to display stop summary if available.
        # Otherwise, just display the reconnect count down.
        if self.cfg.suite and self.stop_summary is None:
            stop_summary = get_stop_state_summary(
                cat_state(self.cfg.suite, self.cfg.host, self.cfg.owner))
            if stop_summary != self.stop_summary:
                self.stop_summary = stop_summary
                self.status = SUITE_STATUS_STOPPED
                gobject.idle_add(
                    self.info_bar.set_stop_summary, stop_summary)
                self.last_update_time = time()
        try:
            update_time_str = get_time_string_from_unix_time(
                self.stop_summary[0]["last_updated"])
        except (AttributeError, IndexError, KeyError, TypeError):
            update_time_str = None
        gobject.idle_add(
            self.info_bar.set_update_time,
            update_time_str, self.info_bar.DISCONNECTED_TEXT)
        gobject.idle_add(self.info_bar.prog_bar_stop)

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
        fam_states = {}
        for fam_id, summary in families.items():
            name, point_string = TaskID.split(fam_id)
            for mem in self.descendants[name]:
                mem_id = TaskID.get(mem, point_string)
                if mem_id in self.state_summary:
                    fam_states[fam_id] = summary
                    break
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
            self.kept_task_ids = set(self.state_summary)
        self.task_list = list(
            set(t['name'] for t in self.state_summary.values()))
        self.task_list.sort()

    def stop(self):
        """Tell self.run to exit."""
        self.quit = True

    def run(self):
        """Start the thread."""
        while not self.quit:
            if self.no_update_event.is_set():
                pass
            elif not self.connect_schd.ready():
                self.info_bar.set_update_time(
                    None,
                    get_seconds_as_interval_string(
                        round(self.connect_schd.dt_next)))
            elif time() > self.next_update_time:
                self.update()
            sleep(1)

    def update(self):
        """Call suite for an update."""
        try:
            gui_summary = self.client.get_gui_summary(full_mode=self.full_mode)
        except ClientError:
            # Bad credential, suite not running, starting up or just stopped?
            if cylc.flags.debug:
                traceback.print_exc()
            self.set_stopped()
            return
        # OK
        if cylc.flags.debug:
            sys.stderr.write("%s CONNECTED - suite cylc version=%s\n" % (
                get_current_time_string(), gui_summary['cylc_version']))
        if gui_summary['full_mode']:
            gobject.idle_add(
                self.app_window.set_title, "%s - %s:%s" % (
                    self.cfg.suite, self.client.host, self.client.port))
            # Connected.
            self.full_mode = False
            self.connected = True
            # This status will be very transient:
            self.set_status(SUITE_STATUS_CONNECTED)

            self.connect_schd.stop()
            if gui_summary['cylc_version'] != CYLC_VERSION:
                gobject.idle_add(self.warn, (
                    "Warning: cylc version mismatch!\n\n"
                    "Suite running with %r.\ngcylc at %r.\n"
                ) % (gui_summary['cylc_version'], CYLC_VERSION))
            self.stop_summary = None
            self.err_log_lines[:] = []

        is_updated = False
        if 'err_content' in gui_summary and 'err_size' in gui_summary:
            self._update_err_log(gui_summary)
            is_updated = True
        if 'ancestors' in gui_summary:
            self.ancestors = gui_summary['ancestors']
            is_updated = True
        if 'ancestors_pruned' in gui_summary:
            self.ancestors_pruned = gui_summary['ancestors_pruned']
            is_updated = True
        if 'descendants' in gui_summary:
            self.descendants = gui_summary['descendants']
            self.all_families = list(self.descendants)
            is_updated = True
        if 'summary' in gui_summary and gui_summary['summary'][0]:
            self._update_state_summary(gui_summary)
            is_updated = True
        if self.status in [SUITE_STATUS_INITIALISING, SUITE_STATUS_STOPPING]:
            gobject.idle_add(self.info_bar.prog_bar_start, self.status)
        elif self.is_reloading:
            gobject.idle_add(self.info_bar.prog_bar_start, "reloading")
        else:
            gobject.idle_add(self.info_bar.prog_bar_stop)
        # Adjust next update duration:
        # If there is an update, readjust to 1.0s or the mean duration of the
        # last 10 main loop. If there is no update, it should be less frequent
        # than the last update duration.  The maximum duration is
        # MAX_UPDATE_DURATION seconds.  This should allow the GUI to update
        # more while the main loop is turning around events quickly, but less
        # frequently during quiet time or when the main loop is busy.
        if is_updated:
            update_duration = 1.0
            self.last_update_time = time()
        else:
            update_duration = time() - self.last_update_time
        if ('mean_main_loop_duration' in gui_summary and
                gui_summary['mean_main_loop_duration'] > update_duration):
            update_duration = gui_summary['mean_main_loop_duration']
        if update_duration > self.MAX_UPDATE_DURATION:
            update_duration = self.MAX_UPDATE_DURATION
        self.next_update_time = time() + update_duration

    def _update_err_log(self, gui_summary):
        """Update suite err log if necessary."""
        self.err_log_lines += gui_summary['err_content'].splitlines()
        self.err_log_lines = self.err_log_lines[-10:]
        gobject.idle_add(
            self.info_bar.set_log, "\n".join(self.err_log_lines),
            gui_summary['err_size'])

    def _update_state_summary(self, gui_summary):
        """Retrieve suite summary."""
        glbl, states, fam_states = gui_summary['summary']
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
        gobject.idle_add(
            self.info_bar.set_state, self.global_summary.get("states", []))
        gobject.idle_add(self.info_bar.set_mode, self.mode)
        gobject.idle_add(self.info_bar.set_update_time, self.update_time_str)
        gobject.idle_add(self.info_bar.set_status, self.status)
