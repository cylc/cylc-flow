#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Functionality for selecting Cylc suite hosts."""

import json
from itertools import dropwhile
from shlex import quote
from random import choice
import socket
from time import sleep

from cylc import LOG
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.exceptions import CylcError
from cylc.hostuserutil import is_remote_host, get_fqdn_by_host
from cylc.remote import remote_cylc_cmd, run_cmd


class EmptyHostList(CylcError):
    """Exception to be raised if there are no valid run hosts.

    Raise if, from the global configuration settings, no hosts are listed
    for potential appointment to run suites (as 'run hosts') or none
    satisfy requirements to pass 'run host select' specifications.

    Print message with the current state of relevant settings for info.
    """

    def __str__(self):
        msg = ("\nNo hosts currently compatible with this global "
               "configuration:")
        suite_server_cfg_items = (['run hosts'], ['run host select', 'rank'],
                                  ['run host select', 'thresholds'])
        for cfg_end_ref in suite_server_cfg_items:
            cfg_end_ref.insert(0, 'suite servers')
            # Add 2-space indentation for clarity in distinction of items.
            msg = '\n  '.join([msg, ' -> '.join(cfg_end_ref) + ':',
                               '  ' + str(glbl_cfg().get(cfg_end_ref))])
        return msg


class HostAppointer(object):
    """Appoint the most suitable host to run a suite on.

    Determine the one host most suitable to (re-)run a suite on from all
    'run hosts' given the 'run host selection' ranking & threshold options
    as specified (else taken as default) in the global configuration.

    Hosts will only be considered if available.

    """

    CMD_BASE = "get-host-metrics"  # 'cylc' prepended by remote_cylc_cmd.
    USE_DISK_PATH = "/"

    def __init__(self, cached=False):
        # get the global config, if cached = False a new config instance will
        # be returned with the up-to-date configuration.
        global_config = glbl_cfg(cached=cached)

        # list the condemned hosts, hosts may be suffixed with `!`
        condemned_hosts = [
            get_fqdn_by_host(host.split('!')[0]) for host in
            global_config.get(['suite servers', 'condemned hosts'])]

        # list configured run hosts eliminating any which cannot be contacted
        # or which are condemned
        self.hosts = []
        for host in (
                global_config.get(['suite servers', 'run hosts']) or
                ['localhost']):
            try:
                if get_fqdn_by_host(host) not in condemned_hosts:
                    self.hosts.append(host)
            except socket.gaierror:
                pass

        # determine the server ranking and acceptance thresholds if configured
        self.rank_method = global_config.get(
            ['suite servers', 'run host select', 'rank'])
        self.parsed_thresholds = self.parse_thresholds(global_config.get(
            ['suite servers', 'run host select', 'thresholds']))

    @staticmethod
    def parse_thresholds(raw_thresholds_spec):
        """Parse raw 'thresholds' global configuration option to dict."""
        if not raw_thresholds_spec:
            return {}

        valid_thresholds = {}
        error_msg = "Invalid suite host threshold component: '%s'"
        for threshold in raw_thresholds_spec.split(';'):
            try:
                measure, cutoff = threshold.strip().split()
                if measure.startswith("load"):
                    valid_thresholds[measure] = float(cutoff)
                elif measure == "memory" or measure.startswith("disk-space"):
                    valid_thresholds[measure] = int(cutoff)
                else:
                    raise ValueError(error_msg % cutoff)
            except ValueError:
                raise ValueError(error_msg % threshold)
        return valid_thresholds

    def selection_complete(self, host_list):
        """Check for and address a list (of hosts) with length zero or one.

        Check length of a list (of hosts); for zero items raise an error,
        for one return that item, else (for multiple items) return False.
        """
        if len(host_list) == 0:
            raise EmptyHostList()
        elif len(host_list) == 1:
            return host_list[0]
        else:
            return False

    def _trivial_choice(self, host_list, ignore_if_thresholds_prov=False):
        """Address run host configuration that can be dealt with trivially.

        If thresholds are not provided or set to be ignored, test if
        'host_list' has length zero or one, else if the ranking method is
        random; if so return an exception or host selected appropriately.
        """
        if ignore_if_thresholds_prov and self.parsed_thresholds:
            return False
        if self.selection_complete(host_list):
            return self.selection_complete(host_list)
        elif self.rank_method == 'random':
            return choice(host_list)
        else:
            return False

    def _get_host_metrics_opts(self):
        """Return 'get-host-metrics' command to run with only required options.

        Return the command string to run 'cylc get host metric' with only
        the required options given rank method and thresholds specified.
        """
        # Convert config keys to associated command options. Ignore 'random'.
        considerations = [self.rank_method] + list(self.parsed_thresholds)
        opts = set()
        for spec in considerations:
            if spec.startswith("load"):
                opts.add("--load")
            elif spec.startswith("disk-space"):
                opts.add("--disk-space=" + self.USE_DISK_PATH)
            elif spec == "memory":
                opts.add("--memory")
        return opts

    def _get_host_metrics(self):
        """Run "cylc get-host-metrics" commands on hosts.

        Return (dict): {host: host-metrics-dict, ...}
        """
        host_stats = {}
        # Run "cylc get-host-metrics" commands on hosts
        host_proc_map = {}
        cmd = [self.CMD_BASE] + sorted(self._get_host_metrics_opts())
        # Start up commands on hosts
        for host in self.hosts:
            if is_remote_host(host):
                host_proc_map[host] = remote_cylc_cmd(
                    cmd, stdin=None, host=host, capture_process=True)
            elif 'localhost' in host_proc_map:
                continue  # Don't duplicate localhost
            else:
                # 1st instance of localhost
                host_proc_map['localhost'] = run_cmd(
                    ['cylc'] + cmd, capture_process=True)
        # Collect results from commands
        while host_proc_map:
            for host, proc in list(host_proc_map.copy().items()):
                if proc.poll() is None:
                    continue
                del host_proc_map[host]
                out, err = (f.decode() for f in proc.communicate())
                if proc.wait():
                    # Command failed in verbose/debug mode
                    LOG.warning(
                        "can't get host metric from '%s'" +
                        "%s  # returncode=%d, err=%s\n",
                        host, ' '.join((quote(item) for item in cmd)),
                        proc.returncode, err)
                else:
                    # Command OK
                    # Users may have profile scripts that write to STDOUT.
                    # Drop all output lines until the the first character of a
                    # line is '{'. Hopefully this is enough to find us the
                    # first line that denotes the beginning of the expected
                    # JSON data structure.
                    out = ''.join(dropwhile(
                        lambda s: not s.startswith('{'), out.splitlines(True)))
                    host_stats[host] = json.loads(out)
            sleep(0.01)
        return host_stats

    def _remove_bad_hosts(self, mock_host_stats=None):
        """Return dictionary of 'good' hosts with their metric stats.

        Run 'get-host-metrics' on each run host in parallel & store extracted
        stats for hosts, else an empty JSON structure. Filter out 'bad' hosts
        whereby either metric data cannot be accessed from the command or at
        least one metric value does not pass a specified threshold.
        """
        if mock_host_stats:  # Create fake data for unittest purposes (only).
            host_stats = dict(mock_host_stats)  # Prevent mutable object issues
        else:
            if not self.hosts:
                return {}
            host_stats = self._get_host_metrics()
        # Analyse get-host-metrics results
        for host, data in list(dict(host_stats).items()):
            if not data:
                # No results for host (command failed) -> skip.
                host_stats.pop(host)
                continue
            for measure, cutoff in self.parsed_thresholds.items():
                datum = data[measure]
                # Cutoff is a minimum or maximum depending on measure context.
                if ((datum > cutoff and measure.startswith("load")) or
                    (datum < cutoff and (
                        measure == "memory" or
                        measure.startswith("disk-space")))):
                    # Alert user that threshold has not been met.
                    LOG.warning(
                        "host '%s' did not pass %s threshold " +
                        "(%s %s threshold %s)\n",
                        host, measure, datum,
                        ">" if measure.startswith("load") else "<", cutoff)
                    host_stats.pop(host)
                    break
        return host_stats

    def _rank_good_hosts(self, all_host_stats):
        """Rank, by specified method, 'good' hosts to return the most suitable.

        Take a dictionary of hosts considered 'good' with the corresponding
        metric data, and rank them via the method specified in the global
        configuration, returning the lowest-ranked (taken as best) host.
        """
        # Convert all dict values from full metrics structures to single
        # metric data values corresponding to the rank method to rank with.
        hosts_with_vals_to_rank = dict(
            (host, metric[self.rank_method])
            for host, metric in all_host_stats.items())
        LOG.debug(
            "INFO: host %s values extracted are: %s",
            self.rank_method,
            "\n".join("  %s: %s" % item
                      for item in hosts_with_vals_to_rank.items()))

        # Sort new dict by value to return ascending-value ordered host list.
        sort_asc_hosts = sorted(
            hosts_with_vals_to_rank, key=hosts_with_vals_to_rank.get)
        base_msg = ("good (metric-returning) hosts were ranked in the "
                    "following order, from most to least suitable: %s")
        if self.rank_method in ("memory", "disk-space:" + self.USE_DISK_PATH):
            # Want 'most free' i.e. highest => reverse asc. list for ranking.
            LOG.debug(base_msg, ', '.join(sort_asc_hosts[::-1]))
            return sort_asc_hosts[-1]
        else:  # A load av. is only poss. left; 'random' dealt with earlier.
            # Want lowest => ranking given by asc. list.
            LOG.debug(base_msg, ', '.join(sort_asc_hosts))
            return sort_asc_hosts[0]

    def appoint_host(self, mock_host_stats=None):
        """Appoint the most suitable host to (re-)run a suite on."""
        if mock_host_stats is None and self.hosts == ['localhost']:
            return 'localhost'
        # Check if immediately 'trivial': no thresholds and zero or one hosts.
        initial_check = self._trivial_choice(
            self.hosts, ignore_if_thresholds_prov=True)
        if initial_check:
            return initial_check

        good_host_stats = self._remove_bad_hosts(mock_host_stats)

        # Re-check for triviality after bad host removal; otherwise must rank.
        pre_rank_check = self._trivial_choice(list(good_host_stats))
        if pre_rank_check:
            return pre_rank_check

        return self._rank_good_hosts(good_host_stats)
