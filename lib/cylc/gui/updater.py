#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
import Pyro
import atexit
import gobject
import threading
from time import sleep, time
import traceback

from cylc.exceptions import PortFileError
import cylc.flags
from cylc.dump import get_stop_state_summary
from cylc.gui.cat_state import cat_state
from cylc.network.suite_state import (
    StateSummaryClient, SuiteStillInitialisingError, get_suite_status_string,
    SUITE_STATUS_NOT_CONNECTED, SUITE_STATUS_CONNECTED,
    SUITE_STATUS_INITIALISING, SUITE_STATUS_STOPPED, SUITE_STATUS_STOPPING)
from cylc.network.suite_info import SuiteInfoClient
from cylc.network.suite_log import SuiteLogClient
from cylc.network.suite_command import SuiteCommandClient
from cylc.wallclock import (
    get_current_time_string,
    get_seconds_as_interval_string,
    get_time_string_from_unix_time)
from cylc.task_id import TaskID
from cylc.version import CYLC_VERSION
from cylc.gui.warning_dialog import warning_dialog
from cylc.task_state import TASK_STATUSES_RESTRICTED


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

        self._summary_update_time = None
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

        client_args = (self.cfg.suite, self.cfg.owner, self.cfg.host,
                       self.cfg.pyro_timeout, self.cfg.port, self.cfg.db,
                       self.cfg.my_uuid)
        self.state_summary_client = StateSummaryClient(*client_args)
        self.suite_info_client = SuiteInfoClient(*client_args)
        self.suite_log_client = SuiteLogClient(*client_args)
        self.suite_command_client = SuiteCommandClient(*client_args)
        # Report sign-out on exit.
        atexit.register(self.state_summary_client.signout)

    def reconnect(self):
        """Try to reconnect to the suite daemon."""
        if cylc.flags.debug:
            print >> sys.stderr, "  reconnection...",
        # Reset Pyro clients.
        self.suite_log_client.reset()
        self.state_summary_client.reset()
        self.suite_info_client.reset()
        self.suite_command_client.reset()
        try:
            self.daemon_version = self.suite_info_client.get_info(
                'get_cylc_version')
        except KeyError:
            self.daemon_version = "??? (pre 6.1.2?)"
            if cylc.flags.debug:
                print >> sys.stderr, "succeeded (old daemon)"
        except PortFileError as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            # Failed to (re)connect.
            # Probably normal shutdown; get a stop summary if available.
            if not self.connect_fail_warned:
                self.connect_fail_warned = True
                gobject.idle_add(self.warn, str(exc))
            if self.cfg.suite and self.stop_summary is None:
                self.stop_summary = get_stop_state_summary(
                    cat_state(self.cfg.suite, self.cfg.host, self.cfg.owner))
                self.last_update_time = time()
            if self.stop_summary is not None and any(self.stop_summary):
                gobject.idle_add(
                    self.info_bar.set_stop_summary, self.stop_summary)
            else:
                self.info_bar.set_update_time(
                    None, self.info_bar.DISCONNECTED_TEXT)
            return
        except Pyro.errors.NamingError as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            return
        except Exception as exc:
            if cylc.flags.debug:
                traceback.print_exc()
            if not self.connect_fail_warned:
                self.connect_fail_warned = True
                if isinstance(exc, Pyro.errors.ConnectionDeniedError):
                    gobject.idle_add(
                        self.warn,
                        "ERROR: %s\n\nIncorrect suite passphrase?" % exc)
                else:
                    gobject.idle_add(self.warn, str(exc))
            return

        gobject.idle_add(
            self.app_window.set_title, "%s - %s:%s" % (
                self.cfg.suite, self.suite_info_client.host,
                self.suite_info_client.port))
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
        try:
            new_err_content, new_err_size = (
                self.suite_log_client.get_err_content(
                    self.err_log_size, self._err_num_log_lines))
        except AttributeError:
            # TODO: post-backwards compatibility concerns, remove this handling
            new_err_content = ""
            new_err_size = self.err_log_size

        err_log_changed = (new_err_size != self.err_log_size)
        if err_log_changed:
            self.err_log_lines += new_err_content.splitlines()
            self.err_log_lines = self.err_log_lines[-self._err_num_log_lines:]
            self.err_log_size = new_err_size
        return err_log_changed

    def retrieve_summary_update_time(self):
        """Retrieve suite summary update time; return True if changed."""
        do_update = False
        try:
            summary_update_time = (
                self.state_summary_client.get_suite_state_summary_update_time()
            )
            if (summary_update_time is None or
                    self._summary_update_time is None or
                    summary_update_time != self._summary_update_time):
                self._summary_update_time = summary_update_time
                do_update = True
        except AttributeError:
            # TODO: post-backwards compatibility concerns, remove this handling
            # Force an update for daemons using the old API
            do_update = True
        return do_update

    def retrieve_state_summaries(self):
        """Retrieve suite summary."""
        glbl, states, fam_states = (
            self.state_summary_client.get_suite_state_summary())
        self.ancestors = self.suite_info_client.get_info(
            'get_first_parent_ancestors')
        self.ancestors_pruned = self.suite_info_client.get_info(
            'get_first_parent_ancestors', True)
        self.descendants = self.suite_info_client.get_info(
            'get_first_parent_descendants')
        self.all_families = self.suite_info_client.get_info('get_all_families')

        self.mode = glbl['run_mode']

        if self.cfg.use_defn_order and 'namespace definition order' in glbl:
            # (protect for compat with old suite daemons)
            nsdo = glbl['namespace definition order']
            if self.ns_defn_order != nsdo:
                self.ns_defn_order = nsdo
                self.dict_ns_defn_order = dict(zip(nsdo, range(0, len(nsdo))))
        try:
            self.update_time_str = get_time_string_from_unix_time(
                glbl['last_updated'])
        except (TypeError, ValueError):
            # Older suite...
            self.update_time_str = glbl['last_updated'].isoformat()
        self.global_summary = glbl

        if self.restricted_display:
            states = self.filter_for_restricted_display(states)

        self.full_state_summary = states
        self.full_fam_state_summary = fam_states
        self.refilter()

        try:
            self.status = glbl['status_string']
        except KeyError:
            # Back compat for suite daemons <= 6.9.1.
            self.status = get_suite_status_string(
                glbl['paused'], glbl['stopping'], glbl['will_pause_at'],
                glbl['will_stop_at'])

        try:
            self.is_reloading = glbl['reloading']
        except KeyError:
            # Back compat.
            pass

    def set_stopped(self):
        """Reset data and clients when suite is stopped."""
        self.connected = False
        self.set_status(SUITE_STATUS_STOPPED)
        self.connect_schd.start()
        self._summary_update_time = None
        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.all_families = {}
        self.global_summary = {}
        self.cfg.port = None
        for client in [self.state_summary_client, self.suite_info_client,
                       self.suite_log_client, self.suite_command_client]:
            if self.cfg.host is None:
                client.host = None
            client.port = None

        if self.cfg.host:
            gobject.idle_add(
                self.app_window.set_title, "%s - %s" % (
                    self.cfg.suite, self.cfg.host))
        else:
            gobject.idle_add(
                self.app_window.set_title, str(self.cfg.suite))

    def set_status(self, status=None):
        """Update status bar."""
        if status is not None:
            self.status = status
        self.info_bar.set_status(self.status)

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
            err_log_changed = self.retrieve_err_log()
            summaries_changed = self.retrieve_summary_update_time()
            if summaries_changed:
                self.retrieve_state_summaries()
        except SuiteStillInitialisingError:
            # Connection achieved but state summary data not available yet.
            if cylc.flags.debug:
                print >> sys.stderr, "  connected, suite initializing ..."
            self.set_status(SUITE_STATUS_INITIALISING)
            if self.info_bar.prog_bar_can_start():
                gobject.idle_add(
                    self.info_bar.prog_bar_start, SUITE_STATUS_INITIALISING)
                self.info_bar.set_state([])
            return False
        except Pyro.errors.NamingError as exc:
            if self.daemon_version is not None:
                # Back compat <= 6.4.0 the state summary object was not
                # connected to Pyro until initialisation was completed.
                if cylc.flags.debug:
                    print >> sys.stderr, (
                        "  daemon <= 6.4.0, suite initializing ...")
                self.set_status(SUITE_STATUS_INITIALISING)
                if self.info_bar.prog_bar_can_start():
                    gobject.idle_add(self.info_bar.prog_bar_start,
                                     SUITE_STATUS_INITIALISING)
                    self.info_bar.set_state([])
                # Reconnect till we get the suite state object.
                self.reconnect()
                return False
            else:
                if cylc.flags.debug:
                    print >> sys.stderr, "  CONNECTION LOST", str(exc)
                self.set_stopped()
                if self.info_bar.prog_bar_active():
                    gobject.idle_add(self.info_bar.prog_bar_stop)
                self.reconnect()
                return False
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
            if (self.status == SUITE_STATUS_STOPPING and
                    self.info_bar.prog_bar_can_start()):
                gobject.idle_add(
                    self.info_bar.prog_bar_start, self.status)
            if (self.is_reloading and
                    self.info_bar.prog_bar_can_start()):
                gobject.idle_add(
                    self.info_bar.prog_bar_start, "reloading")
            if (self.info_bar.prog_bar_active() and
                    not self.is_reloading and
                    self.status not in [SUITE_STATUS_STOPPING,
                                        SUITE_STATUS_INITIALISING]):
                gobject.idle_add(self.info_bar.prog_bar_stop)
            if summaries_changed or err_log_changed:
                return True
            else:
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
        self.info_bar.set_log("\n".join(self.err_log_lines),
                              self.err_log_size)
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
