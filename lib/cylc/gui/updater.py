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

import re
import sys
import gtk
import Pyro
import atexit
import gobject
import threading
from time import sleep, time, ctime

import cylc.flags
from cylc.dump import get_stop_state_summary
from cylc.network.suite_state import (
        StateSummaryClient, SuiteStillInitialisingError)
from cylc.network.suite_info import SuiteInfoClient
from cylc.network.suite_log import SuiteLogClient
from cylc.network.suite_command import SuiteCommandClient
from cylc.task_state import task_state
from cylc.gui.dot_maker import DotMaker
from cylc.wallclock import get_time_string_from_unix_time
from cylc.port_file import PortFileError
from cylc.task_id import TaskID
from cylc.version import CYLC_VERSION
from cylc.gui.warning_dialog import warning_dialog


class PollSchd(object):
    """Keep information on whether the updater should poll or not."""

    DELAYS = {(None, 5): 1, (5, 60): 5, (60, 300): 60, (300, None): 300}

    def __init__(self, start=False):
        """Return a new instance.

        If start is False, the updater can always poll.

        If start is True, the updater should only poll if the ready method
        returns True.

        """

        self.t_init = None
        self.t_prev = None
        if start:
            self.start()

    def ready(self):
        is_ready = self._ready()
        if cylc.flags.debug:
            if not is_ready:
                print >> sys.stderr, "  PollSchd not ready"
        return is_ready

    def _ready(self):
        """Return True if a poll is ready."""
        if self.t_init is None:
            return True
        if self.t_prev is None:
            self.t_prev = time()
            return True
        dt_init = time() - self.t_init
        dt_prev = time() - self.t_prev
        for k, v in self.DELAYS.items():
            lower, upper = k
            if ((lower is None or dt_init >= lower) and
                (upper is None or dt_init < upper)):
                if dt_prev > v:
                    self.t_prev = time()
                    return True
                else:
                    return False
        return True

    def start(self):
        """Start keeping track of latest poll, if not already started."""
        if cylc.flags.debug:
            print >> sys.stderr, '  PollSchd start'
        if self.t_init is None:
            self.t_init = time()
            self.t_prev = None

    def stop(self):
        """Stop keeping track of latest poll."""
        if cylc.flags.debug:
            print >> sys.stderr, '  PollSchd stop'
        self.t_init = None
        self.t_prev = None


class Updater(threading.Thread):

    """Retrieve information about the running or stopped suite."""

    def __init__(self, cfg, info_bar, restricted_display):

        super(Updater, self).__init__()

        self.quit = False

        self.cfg = cfg
        self.info_bar = info_bar

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
        self.triggering_families = {}
        self.global_summary = {}
        self.stop_summary = None
        self.ancestors = {}
        self.ancestors_pruned = {}
        self.descendants = {}
        self.mode = "waiting..."
        self.dt = "waiting..."
        self.dt_date = None
        self.status = None
        self.connected = False
        self.suite_init_warned = False
        self._no_update_event = threading.Event()
        self.poll_schd = PollSchd()
        self._flag_new_update()
        self.ns_defn_order = []
        self.dict_ns_defn_order = {}
        self.restricted_display = restricted_display
        self.filter_name_string = ''
        self.filter_states_excl = []
        self.kept_task_ids = set()
        self.filt_task_ids = set()

        client_args = (
            self.cfg.suite, self.cfg.pphrase, self.cfg.owner, self.cfg.host,
            self.cfg.pyro_timeout, self.cfg.port, self.cfg.my_uuid)
        self.state_summary_client = StateSummaryClient(*client_args)
        self.suite_info_client = SuiteInfoClient(*client_args)
        self.suite_log_client = SuiteLogClient(*client_args)
        self.suite_command_client = SuiteCommandClient(*client_args)
        # Don't report every call to these clients unless in debug mode:
        self.suite_log_client.set_multi()
        self.suite_info_client.set_multi()
        self.state_summary_client.set_multi()
        # Report sign-out on exit.
        atexit.register(self.state_summary_client.signout)

    def _flag_new_update( self ):
        self.last_update_time = time()

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
            daemon_version = self.suite_info_client.get_info_gui('get_cylc_version')
        except KeyError:
            daemon_version = "??? (pre 6.1.2?)"
            if cylc.flags.debug:
                print >> sys.stderr, "succeeded: (old daemon)"
        except (PortFileError,
                Pyro.errors.ProtocolError, Pyro.errors.NamingError) as exc:
            # Not connected.
            if cylc.flags.debug:
                print >> sys.stderr, "failed: %s" % str(exc)
            return False

        # Connected.
        self.status = "connected"
        self.connected = True
        self.poll_schd.stop()
        if cylc.flags.debug:
            print >> sys.stderr, (
                "succeeded: daemon v %s" % daemon_version)
        if daemon_version != CYLC_VERSION:
            gobject.idle_add(self.warn,
                "Warning: cylc version mismatch!\n\n" +
                "Suite running with %r.\n" % daemon_version +
                "gcylc at %r.\n" % CYLC_VERSION
            )
        self.stop_summary = None
        self.err_log_lines = []
        self.err_log_size = 0
        self._flag_new_update()
        # This is an idle_add callback; always return False so that it is only
        # called on the GUI's own update cycle.
        return False

    def set_update(self, should_update):
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
            # TODO: post-backwards compatibility concerns, remove this handling.
            new_err_content = ""
            new_err_size = self.err_log_size

        err_log_changed = (new_err_size != self.err_log_size)
        if err_log_changed:
            self.err_log_lines += new_err_content.splitlines()
            self.err_log_lines = self.err_log_lines[-self._err_num_log_lines:]
            self.err_log_size = new_err_size
        return err_log_changed

    def retrieve_summary_update_time(self):
        """Retrieve suite summary update time; return True if it has changed."""
        do_update = False
        try:
            summary_update_time = (
                self.state_summary_client.get_suite_state_summary_update_time())
            if (summary_update_time is None or
                    self._summary_update_time is None or
                    summary_update_time != self._summary_update_time):
                self._summary_update_time = summary_update_time
                do_update = True
        except AttributeError as e:
            # TODO: post-backwards compatibility concerns, remove this handling.
            # Force an update for daemons using the old API.
            do_update = True
        return do_update

    def retrieve_state_summaries(self):
        glbl, states, fam_states = self.state_summary_client.get_suite_state_summary()
        self.ancestors = self.suite_info_client.get_info_gui('get_first_parent_ancestors')
        self.ancestors_pruned = self.suite_info_client.get_info_gui('get_first_parent_ancestors', True)
        self.descendants = self.suite_info_client.get_info_gui('get_first_parent_descendants')
        self.all_families = self.suite_info_client.get_info_gui('get_all_families')
        self.triggering_families = self.suite_info_client.get_info_gui('get_triggering_families')

        if glbl['stopping']:
            self.status = 'stopping'
        elif glbl['paused']:
            self.status = 'held'
        elif glbl['will_pause_at']:
            self.status = 'hold at ' + glbl[ 'will_pause_at' ]
        elif glbl['will_stop_at']:
            self.status = 'running to ' + glbl[ 'will_stop_at' ]
        else:
            self.status = 'running'
        self.mode = glbl['run_mode']

        if self.cfg.use_defn_order and 'namespace definition order' in glbl: 
            # (protect for compat with old suite daemons)
            nsdo = glbl['namespace definition order']
            if self.ns_defn_order != nsdo:
                self.ns_defn_order = nsdo
                self.dict_ns_defn_order = dict(zip(nsdo, range(0,len(nsdo))))
        try:
            self.dt = get_time_string_from_unix_time(glbl['last_updated'])
        except (TypeError, ValueError):
            # Older suite...
            self.dt = glbl['last_updated'].isoformat()
        self.global_summary = glbl

        if self.restricted_display:
            states = self.filter_for_restricted_display(states)

        self.full_state_summary = states
        self.full_fam_state_summary = fam_states
        self.refilter()

    def get_stop_summary(self):
        # Get the suite stop summary.
        if self.stop_summary is not None and any(self.stop_summary):
            self.info_bar.set_stop_summary(self.stop_summary)
        else:
            self.stop_summary = get_stop_state_summary(
                self.cfg.suite, self.cfg.owner, self.cfg.host)

    def set_stopped(self):
        self.connected = False
        self.status = "stopped"
        self.get_stop_summary()
        self._summary_update_time = None
        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.poll_schd.start()
        self.info_bar.set_state([])
        self.info_bar.set_status(self.status)
        self._flag_new_update()

    def warn(self, msg):
        """Pop up a warning dialog; call on idle_add!"""
        warning_dialog(msg, self.info_bar.get_toplevel()).warn()
        return False

    def update(self):
        if cylc.flags.debug:
            print >> sys.stderr, "UPDATE", ctime().split()[3],
        if not self.connected:
            # Only reconnect via self.reconnect().
            gobject.idle_add(self.reconnect)
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
        except SuiteStillInitialisingError as exc:
            print >> sys.stderr, str(exc)
            if not self.suite_init_warned:
                self.suite_init_warned = True
                gobject.idle_add(self.warn, str(exc))
            self.set_stopped()
            gobject.idle_add(self.reconnect)
            return False
        except (PortFileError,
                Pyro.errors.ProtocolError, Pyro.errors.NamingError) as exc:
            if cylc.flags.debug:
                print >> sys.stderr, "  CONNECTION LOST", str(exc)
            self.set_stopped()
            gobject.idle_add(self.reconnect)
            return False
        else:
            self.suite_init_warned = False
            if summaries_changed or err_log_changed:
                return True
            else:
                return False

    def filter_by_name(self, states):
        return dict(
                (i, j) for i, j in states.items() if
                self.filter_name_string in j['name'] or
                re.search(self.filter_name_string, j['name']))

    def filter_by_state(self, states):
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

    def filter_for_restricted_display(self, states):
        return dict(
                (i, j) for i, j in states.items() if j['state'] in
                task_state.legal_for_restricted_monitoring)

    def refilter(self):
        """filter from the full state summary"""
        if self.filter_name_string or self.filter_states_excl:
            states = self.full_state_summary
            all_ids = set(states.keys())
            if self.filter_name_string:
                states = self.filter_by_name(states)
            if self.filter_states_excl:
                states = self.filter_by_state(states)
            filtered_tasks = set(states.keys())
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
        self.task_list = list(set([t['name'] for t in self.state_summary.values()]))
        self.task_list.sort()

    def update_globals( self ):
        self.info_bar.set_state( self.global_summary.get( "states", [] ) )
        self.info_bar.set_mode( self.mode )
        self.info_bar.set_time( self.dt )
        self.info_bar.set_status( self.status )
        self.info_bar.set_log( "\n".join(self.err_log_lines),
                               self.err_log_size )
        return False

    def stop(self):
        self.quit = True

    def run(self):
        while not self.quit:
            if (not self._no_update_event.is_set()
                and self.poll_schd.ready()
                and self.update()):
                self._flag_new_update()
                gobject.idle_add( self.update_globals )
            sleep(1)
        else:
            pass
