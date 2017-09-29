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
from cylc.cfgspec.gcylc import gcfg
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
    get_seconds_as_interval_string as duration2str,
    get_time_string_from_unix_time as time2str)


class Updater(threading.Thread):

    """Retrieve information about the running or stopped suite."""

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
        self.update_interval = 1.0
        self.max_update_interval = gcfg.get(['maximum update interval'])
        self.status = SUITE_STATUS_NOT_CONNECTED
        self.is_reloading = False
        self.connected = False
        self.no_update_event = threading.Event()
        self.ns_defn_order = []
        self.dict_ns_defn_order = {}
        self.restricted_display = app.restricted_display
        self.filter_name_string = ''
        self.filter_states_excl = []
        self.kept_task_ids = set()
        self.filt_task_ids = set()

        self.version_mismatch_warned = False
        self.client = None

        self.client = None
        # Report sign-out on exit.
        atexit.register(self.signout)

    def signout(self):
        """Sign out the client, if possible."""
        if self.client is not None:
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
        self.update_interval += 1.0
        if self.update_interval > self.max_update_interval:
            self.update_interval = self.max_update_interval
        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.all_families = {}
        self.global_summary = {}
        self.cfg.port = None
        self.client = None
        gobject.idle_add(self.app_window.set_title, str(self.cfg.suite))

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
        prev_update_time = time()
        while not self.quit:
            now = time()
            if self.no_update_event.is_set():
                pass
            elif now > prev_update_time + self.update_interval:
                self.update()
                prev_update_time = time()
            else:
                duration = round(prev_update_time + self.update_interval - now)
                if self.update_interval >= self.max_update_interval:
                    self.info_bar.set_update_time(None, duration2str(duration))
            sleep(1)

    def update(self):
        """Call suite for an update."""
        if self.client is None:
            self.client = SuiteRuntimeServiceClient(
                self.cfg.suite, self.cfg.owner, self.cfg.host, self.cfg.port,
                self.cfg.comms_timeout, self.cfg.my_uuid)
        try:
            my_state = self.client.get_latest_state(full_mode=self.full_mode)
        except ClientError:
            # Bad credential, suite not running, starting up or just stopped?
            if cylc.flags.debug:
                traceback.print_exc()
            self.set_stopped()
            return
        # OK
        if cylc.flags.debug:
            sys.stderr.write("%s CONNECTED - suite cylc version=%s\n" % (
                get_current_time_string(), my_state['cylc_version']))
        self.info_bar.set_update_time(None, None)
        if my_state['full_mode']:
            gobject.idle_add(
                self.app_window.set_title, "%s - %s:%s" % (
                    self.cfg.suite, self.client.host, self.client.port))
            # Connected.
            self.full_mode = False
            self.connected = True
            # This status will be very transient:
            self.set_status(SUITE_STATUS_CONNECTED)

            if my_state['cylc_version'] != CYLC_VERSION:
                gobject.idle_add(self.warn, (
                    "Warning: cylc version mismatch!\n\n"
                    "Suite running with %r.\ngcylc at %r.\n"
                ) % (my_state['cylc_version'], CYLC_VERSION))
            self.stop_summary = None
            self.err_log_lines[:] = []

        is_updated = False
        if 'err_content' in my_state and 'err_size' in my_state:
            self._update_err_log(my_state)
            is_updated = True
        if 'ancestors' in my_state:
            self.ancestors = my_state['ancestors']
            is_updated = True
        if 'ancestors_pruned' in my_state:
            self.ancestors_pruned = my_state['ancestors_pruned']
            is_updated = True
        if 'descendants' in my_state:
            self.descendants = my_state['descendants']
            self.all_families = list(self.descendants)
            is_updated = True
        if 'summary' in my_state and my_state['summary'][0]:
            self._update_state_summary(my_state)
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
        # max_update_interval seconds.  This should allow the GUI to update
        # more while the main loop is turning around events quickly, but less
        # frequently during quiet time or when the main loop is busy.
        if is_updated:
            self.update_interval = 1.0
            self.last_update_time = time()
        elif time() - self.last_update_time > self.update_interval:
            self.update_interval += 1.0
        if ('mean_main_loop_interval' in my_state and
                my_state['mean_main_loop_interval'] > self.update_interval):
            self.update_interval = my_state['mean_main_loop_interval']
        if self.update_interval > self.max_update_interval:
            self.update_interval = self.max_update_interval

    def _update_err_log(self, my_state):
        """Display suite err log info if necessary."""
        self.err_log_lines += my_state['err_content'].splitlines()
        self.err_log_lines = self.err_log_lines[-10:]
        gobject.idle_add(
            self.info_bar.set_log, "\n".join(self.err_log_lines),
            my_state['err_size'])

    def _update_state_summary(self, my_state):
        """Display suite summary."""
        glbl, states, fam_states = my_state['summary']
        self.mode = glbl['run_mode']

        if self.cfg.use_defn_order:
            nsdo = glbl['namespace definition order']
            if self.ns_defn_order != nsdo:
                self.ns_defn_order = nsdo
                self.dict_ns_defn_order = dict(zip(nsdo, range(0, len(nsdo))))

        self.update_time_str = time2str(glbl['last_updated'])
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
