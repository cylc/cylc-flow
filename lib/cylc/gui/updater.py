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

from cylc import cylc_pyro_client, dump
from cylc.task_state import task_state
from cylc.gui.dot_maker import DotMaker
from cylc.state_summary import get_id_summary
from cylc.strftime import strftime
from cylc.wallclock import get_time_string_from_unix_time
from cylc.task_id import TaskID
from cylc.version import CYLC_VERSION  # Warning: will SystemExit on failure.
from warning_dialog import warning_dialog
import gobject
import gtk
import Pyro
import re
import string
import sys
import threading
from time import sleep, time

from cylc import cylc_pyro_client, dump

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
        if self.t_init is None:
            self.t_init = time()
            self.t_prev = None

    def stop(self):
        """Stop keeping track of latest poll."""
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
        self.descendants = []
        self.god = None
        self.mode = "waiting..."
        self.dt = "waiting..."
        self.dt_date = None
        self.status = None
        self.connected = False
        self._no_update_event = threading.Event()
        self.poll_schd = PollSchd()
        self._flag_new_update()
        self._reconnect()
        self.ns_defn_order = []
        self.dict_ns_defn_order = {}
        self.restricted_display = restricted_display
        self.filter_name_string = ''
        self.filter_states_excl = []
        self.kept_task_ids = set()
        self.filt_task_ids = set()

    def _flag_new_update( self ):
        self.last_update_time = time()

    def _retrieve_hierarchy_info(self):
        self.ancestors = self.sinfo.get('first-parent ancestors')
        self.ancestors_pruned = self.sinfo.get('first-parent ancestors', True)
        self.descendants = self.sinfo.get('first-parent descendants')
        self.all_families = self.sinfo.get('all families')
        self.triggering_families = self.sinfo.get('triggering families')

    def _reconnect(self):
        """Connect to the suite daemon and get Pyro client proxies."""
        self.god = None
        self.sinfo = None
        self.log = None
        try:
            client = cylc_pyro_client.client(
                    self.cfg.suite,
                    self.cfg.pphrase,
                    self.cfg.owner,
                    self.cfg.host,
                    self.cfg.pyro_timeout,
                    self.cfg.port )
            self.god = client.get_proxy( 'state_summary' )
            self.sinfo = client.get_proxy( 'suite-info' )
            self.log = client.get_proxy( 'log' )
            self._retrieve_hierarchy_info()
        except Exception, x:
            # (port file not found, if suite not running)
            if self.stop_summary is None:
                self.stop_summary = dump.get_stop_state_summary(
                                                       self.cfg.suite,
                                                       self.cfg.owner,
                                                       self.cfg.host)
                self._flag_new_update()
            return False
        else:
            try:
                daemon_version = self.sinfo.get('get cylc version')
            except KeyError:
                daemon_version = "??? (pre 6.1.2?)"
            if daemon_version != CYLC_VERSION:
                warning_dialog(
                    "Warning: cylc version mismatch!\n\n" +
                    "Suite running with %r.\n" % daemon_version +
                    "gcylc at %r.\n" % CYLC_VERSION,
                    self.info_bar.get_toplevel()
                ).warn()
            self.stop_summary = None
            self.err_log_lines = []
            self.err_log_size = 0
            self.status = "connected"
            self.connected = True
            self.poll_schd.stop()
            self._flag_new_update()
            return True

    def connection_lost( self ):
        self._summary_update_time = None
        self.state_summary = {}
        self.full_state_summary = {}
        self.fam_state_summary = {}
        self.full_fam_state_summary = {}
        self.status = "stopped"
        self.connected = False
        self._flag_new_update()
        self.poll_schd.start()
        self.info_bar.set_state( [] )
        self.info_bar.set_status( self.status )
        if self.stop_summary is not None and any(self.stop_summary):
            self.info_bar.set_stop_summary(self.stop_summary)
        # GTK IDLE FUNCTIONS MUST RETURN FALSE OR WILL BE CALLED MULTIPLE TIMES
        self._reconnect()
        return False

    def set_update( self, should_update ):
        if should_update:
            self._no_update_event.clear()
        else:
            self._no_update_event.set()

    def update(self):
        if self.god is None:
            gobject.idle_add( self.connection_lost )
            return False

        try:
            new_err_content, new_err_size = self.log.get_err_content(
                prev_size=self.err_log_size,
                max_lines=self._err_num_log_lines)
        except (AttributeError, Pyro.errors.NamingError):
            # TODO: post-backwards compatibility concerns, remove this handling.
            new_err_content = ""
            new_err_size = self.err_log_size
        except Pyro.errors.ProtocolError:
            gobject.idle_add( self.connection_lost )
            return False

        err_log_changed = (new_err_size != self.err_log_size)
        if err_log_changed:
            self.err_log_lines += new_err_content.splitlines()
            self.err_log_lines = self.err_log_lines[-self._err_num_log_lines:]
            self.err_log_size = new_err_size

        update_summaries = False
        try:
            summary_update_time = self.god.get_summary_update_time()
            if (summary_update_time is None or
                    self._summary_update_time is None or
                    summary_update_time != self._summary_update_time):
                self._summary_update_time = summary_update_time
                update_summaries = True
        except AttributeError as e:
            # TODO: post-backwards compatibility concerns, remove this handling.
            # Force an update for daemons using the old API.
            update_summaries = True
        except (Pyro.errors.ProtocolError, Pyro.errors.NamingError):
            gobject.idle_add( self.connection_lost )
            return False

        if update_summaries:
            try:
                [glbl, states, fam_states] = self.god.get_state_summary()
                self._retrieve_hierarchy_info() # may change on reload
            except (Pyro.errors.ProtocolError, Pyro.errors.NamingError):
                gobject.idle_add( self.connection_lost )
                return False

            if not glbl:
                self.task_list = []
                return False

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

        if update_summaries or err_log_changed:
            return True
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
