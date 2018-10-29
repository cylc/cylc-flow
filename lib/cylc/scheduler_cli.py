#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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
"""Common logic for "cylc run" and "cylc restart" CLI."""

import os
import json
from pipes import quote
from random import shuffle, choice
import sys
from time import sleep
import unittest

from cylc.cfgspec.glbl_cfg import glbl_cfg
import cylc.flags
from cylc.hostuserutil import get_host, is_remote_host
from cylc.option_parsers import CylcOptionParser as COP
from cylc.remote import remrun, remote_cylc_cmd, run_cmd
from cylc.scheduler import Scheduler
from cylc.suite_srv_files_mgr import (
    SuiteSrvFilesManager, SuiteServiceFileError)

RUN_DOC = r"""cylc [control] run|start [OPTIONS] [ARGS]

Start a suite run from scratch, ignoring dependence prior to the start point.

WARNING: this will wipe out previous suite state. To restart from a previous
state, see 'cylc restart --help'.

The scheduler will run as a daemon unless you specify --no-detach.

If the suite is not already registered (by "cylc register" or a previous run)
it will be registered on the fly before start up.

% cylc run REG
  Run the suite registered with name REG.

% cylc run
  Register $PWD/suite.rc as $(basename $PWD) and run it.
 (Note REG must be given explicitly if START_POINT is on the command line.)

A "cold start" (the default) starts from the suite initial cycle point
(specified in the suite.rc or on the command line). Any dependence on tasks
prior to the suite initial cycle point is ignored.

A "warm start" (-w/--warm) starts from a given cycle point later than the suite
initial cycle point (specified in the suite.rc). Any dependence on tasks prior
to the given warm start cycle point is ignored. The suite initial cycle point
is preserved."""

RESTART_DOC = r"""cylc [control] restart [OPTIONS] ARGS

Start a suite run from the previous state. To start from scratch (cold or warm
start) see the 'cylc run' command.

The scheduler runs as a daemon unless you specify --no-detach.

Tasks recorded as submitted or running are polled at start-up to determine what
happened to them while the suite was down."""

SUITE_NAME_ARG_DOC = ("[REG]", "Suite name")
START_POINT_ARG_DOC = (
    "[START_POINT]",
    "Initial cycle point or 'now';\n" +
    " " * 31 +  # 20 + len("START_POINT")
    "overrides the suite definition.")


def main(is_restart=False):
    """CLI main."""
    options, args = parse_commandline(is_restart)
    if not args:
        # Auto-registration: "cylc run" (no args) in source dir.
        try:
            reg = SuiteSrvFilesManager().register()
        except SuiteServiceFileError as exc:
            sys.exit(exc)
        # Replace this process with "cylc run REG ..." for 'ps -f'.
        os.execv(sys.argv[0], [sys.argv[0]] + [reg] + sys.argv[1:])

    # Check suite is not already running before start of host selection.
    try:
        SuiteSrvFilesManager().detect_old_contact_file(args[0])
    except SuiteServiceFileError as exc:
        sys.exit(exc)

    # Create auth files if needed. On a shared FS if the suite host changes
    # this may (will?) renew the ssl.cert to reflect the change in host name.
    SuiteSrvFilesManager().create_auth_files(args[0])

    # Check whether a run host is explicitly specified, else select one.
    if not options.host:
        host = HostAppointer().appoint_host()
        if is_remote_host(host):
            if is_restart:
                base_cmd = ["restart"] + sys.argv[1:]
            else:
                base_cmd = ["run"] + sys.argv[1:]
            # Prevent recursive host selection
            base_cmd.append("--host=localhost")
            return remote_cylc_cmd(base_cmd, host=host)
    if remrun(set_rel_local=True):  # State localhost as above.
        sys.exit()

    try:
        SuiteSrvFilesManager().get_suite_source_dir(args[0], options.owner)
    except SuiteServiceFileError:
        # Source path is assumed to be the run directory
        SuiteSrvFilesManager().register(
            args[0],
            glbl_cfg().get_derived_host_item(args[0], 'suite run directory'))

    try:
        scheduler = Scheduler(is_restart, options, args)
    except SuiteServiceFileError as exc:
        sys.exit(exc)
    scheduler.start()


def parse_commandline(is_restart):
    """Parse CLI for "cylc run" or "cylc restart"."""
    if is_restart:
        parser = COP(RESTART_DOC, jset=True, argdoc=[SUITE_NAME_ARG_DOC])
    else:
        parser = COP(
            RUN_DOC, jset=True,
            argdoc=[SUITE_NAME_ARG_DOC, START_POINT_ARG_DOC])

    parser.add_option(
        "--non-daemon", help="(deprecated: use --no-detach)",
        action="store_true", default=False, dest="no_detach")

    parser.add_option(
        "-n", "--no-detach", help="Do not daemonize the suite",
        action="store_true", default=False, dest="no_detach")

    parser.add_option(
        "-a", "--no-auto-shutdown", help="Do not shut down"
        " the suite automatically when all tasks have finished."
        " This flag overrides the corresponding suite config item.",
        action="store_true", default=False, dest="no_auto_shutdown")

    parser.add_option(
        "--profile", help="Output profiling (performance) information",
        action="store_true", default=False, dest="profile_mode")

    if is_restart:
        parser.add_option(
            "--checkpoint",
            help="Specify the ID of a checkpoint to restart from",
            metavar="CHECKPOINT-ID", action="store", dest="checkpoint")

        parser.add_option(
            "--ignore-final-cycle-point",
            help=(
                "Ignore the final cycle point in the suite run database. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", default=False, dest="ignore_stop_point")

        parser.add_option(
            "--ignore-initial-cycle-point",
            help=(
                "Ignore the initial cycle point in the suite run database. " +
                "If one is specified in the suite definition it will " +
                "be used, however."),
            action="store_true", default=False, dest="ignore_start_point")
    else:
        parser.add_option(
            "-w", "--warm",
            help="Warm start the suite. "
                 "The default is to cold start.",
            action="store_true", default=False, dest="warm")

        parser.add_option(
            "--ict",
            help="Does nothing, option for backward compatibility only",
            action="store_true", default=False, dest="set_ict")

    parser.add_option(
        "--until",
        help=("Shut down after all tasks have PASSED " +
              "this cycle point."),
        metavar="CYCLE_POINT", action="store", dest="final_point_string")

    parser.add_option(
        "--hold",
        help="Hold (don't run tasks) immediately on starting.",
        action="store_true", default=False, dest="start_held")

    parser.add_option(
        "--hold-after",
        help="Hold (don't run tasks) AFTER this cycle point.",
        metavar="CYCLE_POINT", action="store", dest="hold_point_string")

    parser.add_option(
        "-m", "--mode",
        help="Run mode: live, dummy, dummy-local, simulation (default live).",
        metavar="STRING", action="store", default='live', dest="run_mode",
        choices=["live", "dummy", "dummy-local", "simulation"])

    parser.add_option(
        "--reference-log",
        help="Generate a reference log for use in reference tests.",
        action="store_true", default=False, dest="genref")

    parser.add_option(
        "--reference-test",
        help="Do a test run against a previously generated reference log.",
        action="store_true", default=False, dest="reftest")

    # Override standard parser option for specific help description.
    parser.add_option(
        "--host",
        help="Specify the host on which to start-up the suite. Without this "
        "set a host will be selected using the 'suite servers' global config.",
        metavar="HOST", action="store", dest="host")

    options, args = parser.parse_args()

    if not is_restart and options.warm and len(args) < 2:
        # Warm start must have a start point
        sys.exit(parser.get_usage())

    return options, args


class EmptyHostList(RuntimeError):
    """Exception to be raised if there are no valid run hosts.

    Raise if, from the global configuration settings, no hosts are listed
    for potential appointment to run suites (as 'run hosts') or none
    satisfy requirements to pass 'run host select' specifications.

    Print message with the current state of relevant settings for info.
    """
    def __str__(self):
        msg = ("\nERROR: No hosts currently compatible with this global "
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
    """

    CMD_BASE = "get-host-metrics"  # 'cylc' prepended by remote_cylc_cmd.

    def __init__(self):
        self.use_disk_path = "/"
        self.max_processes = 5
        self.is_debug = cylc.flags.debug or cylc.flags.verbose

        self.hosts = glbl_cfg().get(['suite servers', 'run hosts'])
        self.rank_method = glbl_cfg().get(
            ['suite servers', 'run host select', 'rank'])
        self.parsed_thresholds = self.parse_thresholds(glbl_cfg().get(
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
            if self.is_debug:
                raise EmptyHostList()
            else:
                sys.exit(str(EmptyHostList()))
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
        considerations = [self.rank_method] + self.parsed_thresholds.keys()
        opts = set()
        for spec in considerations:
            if spec.startswith("load"):
                opts.add("--load")
            elif spec.startswith("disk-space"):
                opts.add("--disk-space=" + self.use_disk_path)
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
            for host, proc in host_proc_map.copy().items():
                if proc.poll() is None:
                    continue
                del host_proc_map[host]
                out, err = proc.communicate()
                if not proc.wait():  # Command OK
                    host_stats[host] = json.loads(out)
                elif cylc.flags.verbose or cylc.flags.debug:
                    # Command failed in verbose/debug mode
                    sys.stderr.write((
                        "WARNING: can't get host metric from '%s';"
                        " %s  # returncode=%s, err=%s\n" %
                        (host, ' '.join((quote(item) for item in cmd)),
                         proc.returncode, err)))
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
        for host, data in dict(host_stats).items():
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
                    if self.is_debug:
                        sys.stderr.write((
                            "WARNING: host '%s' did not pass %s threshold "
                            "(%s %s threshold %s)\n" % (
                                host, measure, datum,
                                ">" if measure.startswith("load") else "<",
                                cutoff)))
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
        hosts_with_vals_to_rank = dict((host, metric[self.rank_method]) for
                                       host, metric in all_host_stats.items())
        if self.is_debug:
            print "INFO: host %s values extracted are:" % self.rank_method
            for host, value in hosts_with_vals_to_rank.items():
                print "  " + host + ": " + str(value)

        # Sort new dict by value to return ascending-value ordered host list.
        sort_asc_hosts = sorted(
            hosts_with_vals_to_rank, key=hosts_with_vals_to_rank.get)
        base_msg = ("INFO: good (metric-returning) hosts were ranked in the "
                    "following order, from most to least suitable: ")
        if self.rank_method in ("memory", "disk-space:" + self.use_disk_path):
            # Want 'most free' i.e. highest => reverse asc. list for ranking.
            if self.is_debug:
                sys.stderr.write(
                    base_msg + ', '.join(sort_asc_hosts[::-1]) + '.\n')
            return sort_asc_hosts[-1]
        else:  # A load av. is only poss. left; 'random' dealt with earlier.
            # Want lowest => ranking given by asc. list.
            if self.is_debug:
                sys.stderr.write(base_msg + ', '.join(sort_asc_hosts) + '.\n')
            return sort_asc_hosts[0]

    def appoint_host(self, mock_host_stats=None):
        """Appoint the most suitable host to (re-)run a suite on."""
        if mock_host_stats is None and (
                not self.hosts or self.hosts == ['localhost']):
            return 'localhost'
        # Check if immediately 'trivial': no thresholds and zero or one hosts.
        initial_check = self._trivial_choice(
            self.hosts, ignore_if_thresholds_prov=True)
        if initial_check:
            return initial_check

        good_host_stats = self._remove_bad_hosts(mock_host_stats)

        # Re-check for triviality after bad host removal; otherwise must rank.
        pre_rank_check = self._trivial_choice(good_host_stats.keys())
        if pre_rank_check:
            return pre_rank_check

        return self._rank_good_hosts(good_host_stats)


class TestHostAppointer(unittest.TestCase):
    """Unit tests for the HostAppointer class."""

    def setUp(self):
        """Create HostAppointer class instance to test."""
        self.app = HostAppointer()

    def create_custom_metric(self, disk_int, mem_int, load_floats):
        """Non-test method to create and return a dummy metric for testing.

        Return a structure in the format of 'get_host_metric' output
        containing fake data. 'disk_int' and 'mem_int' should be integers
        and 'load_floats' a list of three floats. Use 'None' instead to not
        add the associated top-level key to metric.
        """
        metric = {}
        if disk_int is not None:  # Distinguish None from '0', value to insert.
            metric.update({'disk-space:' + self.app.use_disk_path: disk_int})
        if mem_int is not None:
            metric.update({"memory": mem_int})
        if load_floats is not None:
            load_1min, load_5min, load_15min = load_floats
            load_data = {
                "load:1": load_1min,
                "load:5": load_5min,
                "load:15": load_15min
            }
            metric.update(load_data)
        return json.dumps(metric)

    def create_mock_hosts(self, N_hosts, initial_values, increments, load_var):
        """Non-test method to create list of tuples of mock hosts and metrics.

        For mock hosts, 'N_hosts' in number, create associated metrics with
        data values that are incremented to create known data variation. The
        list is shuffled to remove ordering by sequence position; name label
        numbers (lower for lower values) indicate the data ordering.
        """
        mock_host_data = []
        for label in range(1, N_hosts + 1):
            val = []
            # Indices {0,1,2} refer to {disk, memory, load} data respectively.
            for index in range(3):
                val.append(
                    initial_values[index] + (label - 1) * increments[index])
            # Load is special as it needs 3 values and they are floats not ints
            val[2] = (val[2], float(val[2]) + load_var,
                      float(val[2]) + 2 * load_var)
            metric = self.create_custom_metric(val[0], val[1], val[2])
            mock_host_data.append(('HOST_' + str(label), json.loads(metric)))
        shuffle(mock_host_data)
        return mock_host_data

    def mock_global_config(self, set_hosts=None, set_rank_method='random',
                           set_thresholds=None):
        """Non-test method to edit global config input to HostAppointer()."""
        if set_hosts is None:
            set_hosts = []
        self.app.hosts = set_hosts
        self.app.rank_method = set_rank_method
        self.app.parsed_thresholds = self.app.parse_thresholds(set_thresholds)

    def setup_test_rank_good_hosts(self, num, init, incr, var):
        """Non-test method to setup routine tests for '_rank_good_hosts'.

        Note:
            * Host list input as arg so not reading from 'self.app.hosts' =>
              only 'set_rank_method' arg to 'mock_global_config' is relevant.
            * rank_method 'random' dealt with before this method is called;
              '_rank_good_hosts' not written to cater for it, so not tested.
            * Mock set {HOST_X} created so that lower X host has lower data
              values (assuming positive 'incr') so for X = {1, ..., N} HOST_1
              or HOST_N is always 'best', depending on rank method context.
        """
        self.mock_global_config(set_rank_method='memory')
        self.assertEqual(
            self.app._rank_good_hosts(dict(
                self.create_mock_hosts(num, init, incr, var))),
            'HOST_' + str(num)
        )
        self.mock_global_config(set_rank_method='disk-space:%s' %
                                self.app.use_disk_path)
        self.assertEqual(
            self.app._rank_good_hosts(dict(
                self.create_mock_hosts(num, init, incr, var))),
            'HOST_' + str(num)
        )
        # Use 'load:5' as test case of load averages. No need to test all.
        self.mock_global_config(set_rank_method='load:5')
        self.assertEqual(
            self.app._rank_good_hosts(dict(
                self.create_mock_hosts(num, init, incr, var))),
            'HOST_1'
        )

    def test_simple(self):
        """Simple end-to-end test of the host appointer."""
        self.mock_global_config()
        self.assertEqual(
            self.app.appoint_host(),
            'localhost'
        )
        self.mock_global_config(set_hosts=['foo'])
        self.assertEqual(
            self.app.appoint_host(),
            'foo'
        )

    def test_parse_thresholds(self):
        """Test the 'parse_thresholds' method."""
        self.mock_global_config()
        self.assertEqual(
            self.app.parse_thresholds(None),
            {}
        )
        self.assertEqual(
            self.app.parse_thresholds("load:5 0.5; load:15 1.0; memory" +
                                      " 100000; disk-space:/ 9999999"),
            {
                "load:5": 0.5,
                "load:15": 1.0,
                "memory": 100000,
                "disk-space:/": 9999999
            }
        )
        self.assertRaises(
            ValueError,
            self.app.parse_thresholds,
            "memory 300000; gibberish 1.0"
        )
        self.assertRaises(
            ValueError,
            self.app.parse_thresholds,
            "load:5 rogue_string"
        )
        # Note lack of semi-colon separator.
        self.assertRaises(
            ValueError,
            self.app.parse_thresholds,
            "disk-space:/ 888 memory 300000"
        )

    def test_trivial_choice(self):
        """Test '_trivial_choice' and by extension 'selection_complete'."""
        self.mock_global_config()  # Case with defaults.
        # assertIn not introduced until Python 2.7, so can't use.
        self.assertTrue(
            self.app._trivial_choice(['HOST_1', 'HOST_2', 'HOST_3'],
                                     ignore_if_thresholds_prov=True) in
            ('HOST_1', 'HOST_2', 'HOST_3')
        )

        # Case of defaults except with rank_method as anything but 'random';
        # really tests 'selection_complete' method (via '_trivial_choice').
        self.mock_global_config(set_rank_method='memory')
        self.assertEqual(
            self.app._trivial_choice(['HOST_1', 'HOST_2', 'HOST_3']),
            False
        )
        self.assertEqual(
            self.app._trivial_choice(['HOST_1']),
            'HOST_1'
        )
        self.assertRaises(
            SystemExit,
            self.app._trivial_choice, []
        )

        # Case with (any) valid thresholds and ignore_if_thresholds_prov=True.
        self.mock_global_config(set_thresholds='memory 10000')
        self.assertEqual(
            self.app._trivial_choice(['HOST_1', 'HOST_2', 'HOST_3'],
                                     ignore_if_thresholds_prov=True),
            False
        )

    def test_get_host_metrics_opts(self):
        """Test the '_get_host_metrics_opts' method."""
        self.mock_global_config()
        self.assertEqual(self.app._get_host_metrics_opts(), set())
        self.mock_global_config(set_thresholds='memory 1000')
        self.assertEqual(
            self.app._get_host_metrics_opts(), set(['--memory']))
        self.mock_global_config(set_rank_method='memory')
        self.assertEqual(
            self.app._get_host_metrics_opts(), set(['--memory']))
        self.mock_global_config(
            set_rank_method='disk-space:%s' % self.app.use_disk_path,
            set_thresholds='load:1 1000')
        self.assertEqual(
            self.app._get_host_metrics_opts(),
            set(['--disk-space=' + self.app.use_disk_path, '--load']),
        )
        self.mock_global_config(
            set_rank_method='memory',
            set_thresholds='disk-space:/ 1000; memory 1000; load:15 1.0')
        # self.parsed_thresholds etc dict => unordered keys: opts order varies;
        # instead of cataloging all combos or importing itertools, test split.
        self.assertEqual(
            self.app._get_host_metrics_opts(),
            set(['--disk-space=/', '--load', '--memory']),
        )

    def test_remove_bad_hosts(self):
        """Test the '_remove_bad_hosts' method.

        Test using 'localhost' only since remote host functionality is
        contained only inside remote_cylc_cmd() so is outside of the scope
        of HostAppointer.
        """
        self.mock_global_config(set_hosts=['localhost'])
        self.failUnless(self.app._remove_bad_hosts().get('localhost', False))
        # Test 'localhost' true identifier is treated properly too.
        self.mock_global_config(set_hosts=[get_host()])
        self.failUnless(self.app._remove_bad_hosts().get('localhost', False))

        self.mock_global_config(set_hosts=['localhost', 'FAKE_HOST'])
        # Check for no exceptions and 'localhost' but not 'FAKE_HOST' data
        # Difficult to unittest for specific stderr string; this is sufficient.
        self.failUnless(self.app._remove_bad_hosts().get('localhost', False))
        self.failUnless(self.app._remove_bad_hosts().get('FAKE_HOST', True))

        # Apply thresholds impossible to pass; check results in host removal.
        self.mock_global_config(
            set_hosts=['localhost'], set_thresholds='load:15 0.0')
        self.assertEqual(self.app._remove_bad_hosts(), {})
        self.mock_global_config(
            set_hosts=['localhost'], set_thresholds='memory 1000000000')
        self.assertEqual(self.app._remove_bad_hosts(), {})

    def test_rank_good_hosts(self):
        """Test the '_rank_good_hosts' method."""

        # Considering special cases:
        # Case with 0 or 1 hosts filtered out before method called, so ignore.
        # Variation in load averages is irrelevant; no need to test lack of.

        # Case with no increments => same stats for all hosts. Random result.
        self.mock_global_config(set_rank_method='memory')  # Any except random.
        self.assertTrue(
            self.app._rank_good_hosts(dict(
                self.create_mock_hosts(
                    5, [100, 100, 1.0], [0, 0, 0.0], 0.1))) in
            ('HOST_1', 'HOST_2', 'HOST_3', 'HOST_4', 'HOST_5')
        )

        # Test a selection of routine cases; only requirements are for types:
        # init and incr in form [int, int, float] and int var, and for size:
        # num > 1, all elements of init > 0(.0) and incr >= 0(.0), var >= 0.0.
        self.setup_test_rank_good_hosts(
            2, [100, 100, 1.0], [100, 100, 1.0], 0.2)
        self.setup_test_rank_good_hosts(
            10, [500, 200, 0.1], [100, 10, 10.0], 0.0)
        self.setup_test_rank_good_hosts(
            10, [103870, 52139, 3.19892], [5348, 45, 5.2321], 0.52323)
        self.setup_test_rank_good_hosts(
            50, [10000, 20000, 0.00000001], [400, 1000000, 1.1232982], 0.11)

    def test_appoint_host(self):
        """Test the 'appoint_host' method.

        This method calls all other methods in the class directly or
        indirectly, hence this is essentially a full-class test. The
        following phase space is covered:

            1. Number of hosts: none, one or multiple.
            2. Rank method: random, load (use just 5 min average case),
                            memory or disk space.
            3. Thresholds: without or with, including all measures.
        """
        # Define phase space.
        hosts_space = ([], ['HOST_1'],
                       ['HOST_1', 'HOST_2', 'HOST_3', 'HOST_4', 'HOST_5'])
        rank_method_space = ('random', 'load:5', 'memory', 'disk-space:/')
        thresholds_space = (None, 'load:1 2.0; load:5 1.10; load:15' +
                            ' 1.31; memory 31000; disk-space:/ 1000')

        # Enumerate all (24) correct results required to test equality with.
        # Correct results deduced individually based on mock host set. Note
        # only HOST_2 and HOST_3 pass all thresholds for thresholds_space[1].
        correct_results = (8 * [SystemExit] +
                           4 * ['HOST_1', SystemExit] +
                           ['HOST_X', 'HOST_Y', 'HOST_1', 'HOST_2', 'HOST_5',
                            'HOST_3', 'HOST_5', 'HOST_3'])

        for index, (host_list, method, thresholds) in enumerate(
                [(hosts, meth, thr) for hosts in hosts_space for meth in
                 rank_method_space for thr in thresholds_space]):

            # Use same group of mock hosts each time, but ensure compatible
            # number (at host_list changeover only; avoid re-creating same).
            if index in (0, 8, 16):
                mock_host_stats = dict(self.create_mock_hosts(
                    len(host_list), [400000, 30000, 0.05], [50000, 1000, 0.2],
                    0.4))

            self.mock_global_config(
                set_hosts=host_list, set_rank_method=method,
                set_thresholds=thresholds)

            if correct_results[index] == 'HOST_X':  # random, any X={1..5} fine
                self.assertTrue(
                    self.app.appoint_host(mock_host_stats) in host_list)
            elif correct_results[index] == 'HOST_Y':  # random + thr, X={2,3}
                self.assertTrue(
                    self.app.appoint_host(mock_host_stats) in host_list[1:3])
            elif isinstance(correct_results[index], str):
                self.assertEqual(
                    self.app.appoint_host(mock_host_stats),
                    correct_results[index]
                )
            else:
                self.assertRaises(
                    correct_results[index],
                    self.app.appoint_host,
                    mock_host_stats
                )


if __name__ == "__main__":
    unittest.main()
