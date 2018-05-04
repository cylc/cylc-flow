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
"""Run command on a remote, (i.e. a remote [user@]host)."""

import os
import sys
import shlex
import signal
import unittest
import json
import socket
from time import sleep
from pipes import quote
from posix import WIFSIGNALED
from random import shuffle, choice
from multiprocessing import Pool

# CODACY ISSUE:
#   Consider possible security implications associated with Popen module.
# REASON IGNORED:
#   Subprocess is needed, but we use it with security in mind.
from subprocess import Popen, PIPE, CalledProcessError

import cylc.flags
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.version import CYLC_VERSION
from cylc.hostuserutil import get_fqdn_by_host


def get_proc_ancestors():
    """Return list of parent PIDs back to init."""
    pid = os.getpid()
    ancestors = []
    while True:
        p = Popen(["ps", "-p", str(pid), "-oppid="], stdout=PIPE, stderr=PIPE)
        ppid = p.communicate()[0].strip()
        if not ppid:
            return ancestors
        ancestors.append(ppid)
        pid = ppid


def watch_and_kill(proc):
    """ Kill proc if my PPID (etc.) changed - e.g. ssh connection dropped."""
    gpa = get_proc_ancestors()
    while True:
        sleep(0.5)
        if proc.poll() is not None:
            break
        if get_proc_ancestors() != gpa:
            sleep(1)
            os.kill(proc.pid, signal.SIGTERM)
            break


def run_ssh_cmd(command, stdin=None, capture_process=False,
                capture_status=False, manage=False):
    """Run a given cylc command on another account and/or host.

    Arguments:
        command (list):
            command inclusive of all opts and args required to run via ssh.
        stdin (file):
            If specified, it should be a readable file object.
            If None, `open(os.devnull)` is set if output is to be captured.
        capture_process (boolean):
            If True, set stdout=PIPE and return the Popen object.
        capture_status (boolean):
            If True, and the remote command is unsuccessful, return the
            associated exit code instead of exiting with an error.
        manage (boolean):
            If True, watch ancestor processes and kill command if they change
            (e.g. kill tail-follow commands when parent ssh connection dies).

    Return:
        * If capture_process=True, the Popen object if created successfully.
        * Else True if the remote command is executed successfully, or
          if unsuccessful and capture_status=True the remote command exit code.
        * Otherwise exit with an error message."""

    # CODACY ISSUE:
    #   subprocess call - check for execution of untrusted input.
    # REASON IGNORED:
    #   The command is read from the site/user global config file, but we check
    #   above that it ends in 'cylc', and in any case the user could execute
    #   any such command directly via ssh.
    stdout = None
    if capture_process:
        stdout = PIPE
        if stdin is None:
            stdin = open(os.devnull)

    try:
        popen = Popen(command, stdin=stdin, stdout=stdout)
    except OSError as exc:
        sys.exit(r'ERROR: remote command invocation failed %s' % exc)

    if capture_process:
        return popen
    else:
        if manage:
            watch_and_kill(popen)
        res = popen.wait()
        if WIFSIGNALED(res):
            sys.exit(r'ERROR: remote command terminated by signal %d' % res)
        elif res and capture_status:
            return res
        elif res:
            sys.exit(r'ERROR: remote command failed %d' % res)
        else:
            return True


def construct_ssh_cmd(raw_cmd, user=None, host=None, forward_x11=False,
                      set_stdin=False, ssh_login_shell=None, ssh_cylc=None,
                      set_UTC=False, allow_flag_opts=False):
    """Append a bare command with further options required to run via ssh.

    Arguments:
        raw_cmd (list): primitive command to run remotely.
        user (string): user ID for the remote login.
        host (string): remote host name. Use 'localhost' if not specified.
        forward_x11 (boolean):
            If True, use 'ssh -Y' to enable X11 forwarding, else just 'ssh'.
        set_stdin (file):
            If None, the `-n` option will be added to the SSH command line.
        ssh_login_shell (boolean):
            If True, launch remote command with `bash -l -c 'exec "$0" "$@"'`.
        ssh_cylc (string):
            Location of the remote cylc executable.
        set_UTC (boolean):
            If True, check UTC mode and specify if set to True (non-default).
        allow_flag_opts (boolean):
            If True, check CYLC_DEBUG and CYLC_VERBOSE and if non-default,
            specify debug and/or verbosity as options to the 'raw cmd'.

    Return:
        A list containing a chosen command including all arguments and options
        necessary to directly execute the bare command on a given host via ssh.
    """
    command = shlex.split(glbl_cfg().get_host_item('ssh command', host, user))

    if forward_x11:
        command.append('-Y')
    if set_stdin is None:
        command.append('-n')

    user_at_host = ''
    if user:
        user_at_host = user + '@'
    if host:
        user_at_host += host
    else:
        user_at_host += 'localhost'
    command.append(user_at_host)

    # Pass cylc version (and optionally UTC mode) through.
    command += ['env', quote(r'CYLC_VERSION=%s' % CYLC_VERSION)]
    if set_UTC and os.getenv('CYLC_UTC') in ["True", "true"]:
        command.append(quote(r'CYLC_UTC=True'))
        command.append(quote(r'TZ=UTC'))

    # Use bash -l?
    if ssh_login_shell is None:
        ssh_login_shell = glbl_cfg().get_host_item(
            'use login shell', host, user)
    if ssh_login_shell:
        # A login shell will always source /etc/profile and the user's bash
        # profile file. To avoid having to quote the entire remote command
        # it is passed as arguments to the bash script.
        command += ['bash', '--login', '-c', quote(r'exec "$0" "$@"')]

    # 'cylc' on the remote host
    if ssh_cylc:
        command.append(ssh_cylc)
    else:
        ssh_cylc = glbl_cfg().get_host_item('cylc executable', host, user)
        if ssh_cylc.endswith('cylc'):
            command.append(ssh_cylc)
        else:
            raise ValueError(
                r'ERROR: bad cylc executable in global config: %s' % ssh_cylc)

    # Insert core raw command after ssh, but before its own, command options.
    command += raw_cmd

    if allow_flag_opts:
        if (cylc.flags.verbose or os.getenv('CYLC_VERBOSE') in
                ["True", "true"]):
            command.append(r'--verbose')
        if cylc.flags.debug or os.getenv('CYLC_DEBUG') in ["True", "true"]:
            command.append(r'--debug')
    if cylc.flags.debug:
        sys.stderr.write(' '.join(quote(c) for c in command) + '\n')

    return command


def remote_cylc_cmd(
        cmd, user=None, host=None, stdin=None, ssh_login_shell=None,
        ssh_cylc=None, capture=False, manage=False):
    """Run a given cylc command on another account and/or host.

    Arguments:
    Args are directly inputted to one of two functions; see those docstrings:
            * See 'construct_ssh_cmd()' docstring:
                * cmd (--> raw_cmd);
                * user;
                * host;
                * stdin (--> set_stdin) [see also below];
                * ssh_login_shell;
                * ssh_cylc.
            * See 'run_ssh_cmd()' docstring:
                * stdin [see also above]
                * capture (--> capture_process);
                * manage.

    Return:
        If capture=True, return the Popen object if created successfully.
        Otherwise, return the exit code of the remote command."""
    command = construct_ssh_cmd(
        cmd, user=user, host=host, set_stdin=stdin,
        ssh_login_shell=ssh_login_shell, ssh_cylc=ssh_cylc)

    return run_ssh_cmd(command, stdin=stdin, capture_process=capture,
                       capture_status=True, manage=manage)


def remrun(dry_run=False, forward_x11=False, abort_if=None):
    """Short for RemoteRunner().execute(...)"""
    return RemoteRunner().execute(dry_run, forward_x11, abort_if)


class RemoteRunner(object):
    """Run current command on a remote host.

    If owner or host differ from username and localhost, strip the
    remote options from the commandline and reinvoke the command on the
    remote host by non-interactive ssh, then exit; else do nothing.

    To ensure that users are aware of remote re-invocation info is always
    printed, but to stderr so as not to interfere with results.

    """

    def __init__(self, argv=None):
        self.owner = None
        self.host = None
        self.ssh_login_shell = None
        self.ssh_cylc = None
        self.argv = argv or sys.argv

        cylc.flags.verbose = '-v' in self.argv or '--verbose' in self.argv

        # Detect and replace host and owner options
        argv = self.argv[1:]
        self.args = []
        while argv:
            arg = argv.pop(0)
            if arg.startswith('--user='):
                self.owner = arg.replace('--user=', '')
            elif arg.startswith('--host='):
                self.host = arg.replace('--host=', '')
            elif arg.startswith('--ssh-cylc='):
                self.ssh_cylc = arg.replace('--ssh-cylc=', '')
            elif arg == '--login':
                self.ssh_login_shell = True
            elif arg == '--no-login':
                self.ssh_login_shell = False
            else:
                self.args.append(arg)

        if self.owner is None and self.host is None:
            self.is_remote = False
        else:
            from cylc.hostuserutil import is_remote
            self.is_remote = is_remote(self.host, self.owner)

    def execute(self, dry_run=False, forward_x11=False, abort_if=None):
        """Execute command on remote host.

        Returns False if remote re-invocation is not needed, True if it is
        needed and executes successfully otherwise aborts."""
        if not self.is_remote:
            return False

        if abort_if is not None and abort_if in sys.argv:
            sys.stderr.write(
                "ERROR: option '%s' not available for remote run\n" % abort_if)
            return True

        cmd = [os.path.basename(self.argv[0])[5:]]  # /path/to/cylc-foo => foo
        for arg in self.args:
            cmd.append(quote(arg))
            # above: args quoted to avoid interpretation by the shell,
            # e.g. for match patterns such as '.*' on the command line.

        command = construct_ssh_cmd(
            cmd, user=self.owner, host=self.host, forward_x11=forward_x11,
            ssh_login_shell=self.ssh_login_shell, ssh_cylc=self.ssh_cylc,
            set_UTC=True, allow_flag_opts=True)

        if dry_run:
            return command
        else:
            return run_ssh_cmd(command)


class EmptyHostList(Exception):
    """Exception to be raised if there are no valid run hosts.

       Raise if, from the global configuration settings, no hosts are listed
       for potential appointment to run suites (as 'run hosts') or none
       satisfy requirements to pass 'run host select' specifications.

       Print message with the current state of relevant settings for info."""

    def __str__(self):
        msg = "No hosts currently compatible with this global configuration:\n"
        suite_server_cfg_items = (['run hosts'], ['run host select', 'rank'],
                                  ['run host select', 'thresholds'])
        for cfg_end_ref in suite_server_cfg_items:
            cfg_full_ref = cfg_end_ref.insert(0, 'suite servers')
            # Add 2-space indentation for clarity in distinction of items.
            msg = '\n  '.join([msg, cfg_item[-1] + ':',
                               '  ' + glbl_cfg().get(cfg_full_ref)])
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

        try:
            self.HOSTS = glbl_cfg().get(['suite servers', 'run hosts'])
            self.RANK_METHOD = glbl_cfg().get(
                ['suite servers', 'run host select', 'rank'])
            self.THRESHOLDS = glbl_cfg().get(
                ['suite servers', 'run host select', 'thresholds'])
        except KeyError:  # Catch for unittest which updates these internally.
            self.HOSTS = []
            self.RANK_METHOD = 'random'
            self.THRESHOLDS = None

        self.PARSED_THRESHOLDS = self.parse_thresholds(self.THRESHOLDS)

    @staticmethod
    def parse_thresholds(raw_thresholds_spec):
        """Parse raw 'thresholds' global configuration option to dict."""
        if not raw_thresholds_spec:
            return {}
        valid_thresholds = {}
        for threshold in raw_thresholds_spec.split(';'):
            threshold = threshold.strip()
            try:
                measure, cutoff = threshold.split(' ')
            except (AttributeError, ValueError):
                raise AttributeError(
                    "Invalid threshold component '%s'." % threshold)
            try:
                if measure.startswith("load"):
                    cutoff = float(cutoff)
                elif measure == "memory" or measure.startswith("disk-space"):
                    cutoff = int(cutoff)
                else:
                    raise AttributeError("Invalid threshold measure '%s'." %
                                         measure)
            except ValueError:
                raise ValueError(
                    "Threshold value '%s' of wrong type." % cutoff)
            else:
                valid_thresholds[measure] = cutoff
        return valid_thresholds

    @staticmethod
    def selection_complete(host_list):
        """Check for and address a list (of hosts) with length zero or one.

           Check length of a list (of hosts); for zero items raise an error,
           for one return that item, else (for multiple items) return False."""
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
           random; if so return an exception or host selected appropriately."""
        if ignore_if_thresholds_prov and self.PARSED_THRESHOLDS:
            return False
        if self.selection_complete(host_list):
            return self.selection_complete(host_list)
        elif self.RANK_METHOD == 'random':
            return choice(host_list)
        else:
            return False

    def _process_get_host_metrics_cmd(self):
        """Return 'get_host_metrics' command to run with only required options.

           Return the command string to run 'cylc get host metric' with only
           the required options given rank method and thresholds specified."""

        # Convert config keys to associated command options. Ignore 'random'.
        considerations = [self.RANK_METHOD] + self.PARSED_THRESHOLDS.keys()
        opts = set()
        for spec in considerations:
            if spec.startswith("load"):
                opts.add("--load")
            elif spec.startswith("disk-space"):
                opts.add("--disk-space=" + self.use_disk_path)
            elif spec == "memory":
                opts.add("--memory")

        cmd = [self.CMD_BASE] + list(opts)
        return " ".join(cmd)

    def _remove_bad_hosts(self, cmd_with_opts, mock_stats=False):
        """Return dictionary of 'good' hosts with their metric stats.

           Run 'get-host-metrics' on each run host in parallel & store
           extracted stats for 'good' hosts only. Ignore 'bad' hosts whereby
           either metric data cannot be accessed from the command or at least
           one metric value does not pass a specified threshold."""
        host_stats = {}
        cmd = cmd_with_opts.split()
        if mock_stats:  # Create fake data for unittest purposes (only).
            host_stats = dict(mock_stats)  # Prevent mutable object issues.
        else:
            hosts = list(self.HOSTS)  # copy for safety.
            processes = min(len(hosts), self.max_processes)
            ordered_results = process_pool(processes, _process_host_unpack,
                                           zip(hosts, len(hosts) * [cmd]))
            proc_hosts = dict(zip(hosts, ordered_results))
            host_stats = [dict(host, metr) for host, metr in
                          proc_hosts.items() if metr is not None]

        bad_hosts = []  # Get errors if alter dict during iteration. Use list.
        for host in host_stats:
            for measure, cutoff in self.PARSED_THRESHOLDS.items():
                datum = host_stats[host][measure]
                # Cutoff is a minimum or maximum depending on measure context.
                if ((datum > cutoff and measure.startswith("load")) or
                        (datum < cutoff and (measure == "memory" or
                         measure.startswith("disk-space")))):
                    bad_hosts.append(host)
                    continue
        return dict((host, metr) for host, metr in
                    host_stats.items() if host not in bad_hosts)

    def _rank_good_hosts(self, all_host_stats):
        """Rank, by specified method, 'good' hosts to return the most suitable.

           Take a dictionary of hosts considered 'good' with the corresponding
           metric data, and rank them via the method specified in the global
           configuration, returning the lowest-ranked (taken as best) host."""

        # Convert all dict values from full metrics structures to single
        # metric data values corresponding to the rank method to rank with.
        hosts_with_vals_to_rank = dict((host, metric[self.RANK_METHOD]) for
                                       host, metric in all_host_stats.items())

        # Rank new dict by value and return list of hosts (only) in rank order.
        sort_asc_hosts = sorted(
            hosts_with_vals_to_rank, key=hosts_with_vals_to_rank.get)
        if self.RANK_METHOD in ("memory", "disk-space:" + self.use_disk_path):
            # Want 'most free' i.e. highest => final host in asc. list.
            return sort_asc_hosts[-1]
        else:  # A load av. is only poss. left; 'random' dealt with earlier.
            return sort_asc_hosts[0]  # Want lowest => first host in asc. list.

    def appoint_host(self, override_stats=False):
        """Appoint the most suitable host to (re-)run a suite on."""

        # Check if immediately 'trivial': no thresholds and zero or one hosts.
        initial_check = self._trivial_choice(
            self.HOSTS, ignore_if_thresholds_prov=True)
        if initial_check:
            return initial_check

        good_host_stats = self._remove_bad_hosts(
            self._process_get_host_metrics_cmd(), mock_stats=override_stats)

        # Re-check for triviality after bad host removal; otherwise must rank.
        pre_rank_check = self._trivial_choice(good_host_stats.keys())
        if pre_rank_check:
            return pre_rank_check

        return self._rank_good_hosts(good_host_stats)


class TestHostAppointer(unittest.TestCase):
    """Unit tests for the HostAppointer class."""

    def setUp(self):
        """Create variables and templates to use in tests."""
        self.app = HostAppointer()

    def create_custom_metric(self, disk_int, mem_int, load_floats):
        """Non-test method to create and return a dummy metric for testing.

           Return a structure in the format of 'get_host_metric' output
           containing fake data. 'disk_int' and 'mem_int' should be integers
           and 'load_floats' a list of three floats. Use 'None' instead to not
           add the associated top-level key to metric."""
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
           numbers (lower for lower values) indicate the data ordering."""
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
        self.app.HOSTS = set_hosts
        self.app.RANK_METHOD = set_rank_method
        self.app.PARSED_THRESHOLDS = self.app.parse_thresholds(set_thresholds)

    def setup_test_rank_good_hosts(self, num, init, incr, var):
        """Non-test method to setup routine tests for '_rank_good_hosts'.

           Note:
           * Host list input as arg so not reading from 'self.app.HOSTS' =>
             only 'set_rank_method' arg to 'mock_global_config' is relevant.
           * RANK_METHOD 'random' dealt with before this method is called;
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
            AttributeError,
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
            AttributeError,
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

        # Case of defaults except with RANK_METHOD as anything but 'random';
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
            EmptyHostList,
            self.app._trivial_choice, []
        )

        # Case with (any) valid thresholds and ignore_if_thresholds_prov=True.
        self.mock_global_config(set_thresholds='memory 10000')
        self.assertEqual(
            self.app._trivial_choice(['HOST_1', 'HOST_2', 'HOST_3'],
                                     ignore_if_thresholds_prov=True),
            False
        )

    def test_process_get_host_metric_cmd(self):
        """Test the '_process_get_host_metrics_cmd' method."""
        self.mock_global_config()
        self.assertEqual(
            self.app._process_get_host_metrics_cmd(),
            'get-host-metrics'
        )
        self.mock_global_config(set_thresholds='memory 1000')
        self.assertEqual(
            self.app._process_get_host_metrics_cmd(),
            'get-host-metrics --memory'
        )
        self.mock_global_config(set_rank_method='memory')
        self.assertEqual(
            self.app._process_get_host_metrics_cmd(),
            'get-host-metrics --memory'
        )
        self.mock_global_config(
            set_rank_method='disk-space:%s' % self.app.use_disk_path,
            set_thresholds='load:1 1000')
        self.assertEqual(
            self.app._process_get_host_metrics_cmd(),
            'get-host-metrics --disk-space=' + self.app.use_disk_path +
            ' --load'
        )
        self.mock_global_config(
            set_rank_method='memory',
            set_thresholds='disk-space:/ 1000; memory 1000; load:15 1.0')
        # self.PARSED_THRESHOLDS etc dict => unordered keys: opts order varies;
        # instead of cataloging all combos or importing itertools, test split.
        self.assertEqual(
            set(self.app._process_get_host_metrics_cmd().split()),
            set(['get-host-metrics', '--memory', '--disk-space=/', '--load'])
        )

    def test_remove_bad_hosts(self):
        """Test the '_remove_bad_hosts' method.

           Test using 'localhost' only since remote host functionality is
           contained only inside remote_cylc_cmd() so is outside of the scope
           of HostAppointer."""
        self.mock_global_config(set_hosts=['localhost'])
        self.failUnless(
            self.app._remove_bad_hosts(
                self.app.CMD_BASE).get('localhost', False)
        )
        # Test 'localhost' true identifier is treated properly too.
        self.mock_global_config(set_hosts=[get_fqdn_by_host('localhost')])
        self.failUnless(
            self.app._remove_bad_hosts(
                self.app.CMD_BASE).get(get_fqdn_by_host('localhost'), False)
        )

        self.mock_global_config(set_hosts=['localhost', 'FAKE_HOST'])
        # Check for no exceptions and 'localhost' but not 'FAKE_HOST' data
        # Difficult to unittest for specific stderr string; this is sufficient.
        self.failUnless(
            self.app._remove_bad_hosts(
                self.app.CMD_BASE).get('localhost', False)
        )
        self.failUnless(
            not self.app._remove_bad_hosts(
                self.app.CMD_BASE).get('FAKE_HOST', False)
        )
        self.mock_global_config(set_hosts=['localhost'])  # see above RE stderr
        self.assertEqual(
            self.app._remove_bad_hosts(self.app.CMD_BASE + ' --nonsense'),
            {}
        )

        # Apply thresholds impossible to pass; check results in host removal.
        self.mock_global_config(
            set_hosts=['localhost'], set_thresholds='load:15 0.0')
        self.assertEqual(
            self.app._remove_bad_hosts(self.app.CMD_BASE + " --load"),
            {}
        )
        self.mock_global_config(
            set_hosts=['localhost'], set_thresholds='memory 1000000000')
        self.assertEqual(
            self.app._remove_bad_hosts(self.app.CMD_BASE + " --memory"),
            {}
        )

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
        correct_results = (8 * [EmptyHostList] +
                           4 * ['HOST_1', EmptyHostList] +
                           ['HOST_X', 'HOST_Y', 'HOST_1', 'HOST_2', 'HOST_5',
                            'HOST_3', 'HOST_5', 'HOST_3'])

        for index, (host_list, method, thresholds) in enumerate(
                [(hosts, meth, thr) for hosts in hosts_space for meth in
                 rank_method_space for thr in thresholds_space]):

            # Use same group of mock hosts each time, but ensure compatible
            # number (at host_list changeover only; avoid re-creating same).
            if index in (0, 8, 16):
                mock_hosts = dict(self.create_mock_hosts(
                    len(host_list), [400000, 30000, 0.05], [50000, 1000, 0.2],
                    0.4))

            self.mock_global_config(
                set_hosts=host_list, set_rank_method=method,
                set_thresholds=thresholds)

            if correct_results[index] == 'HOST_X':  # random, any X={1..5} fine
                self.assertTrue(
                    self.app.appoint_host(override_stats=mock_hosts) in
                    host_list
                )
            elif correct_results[index] == 'HOST_Y':  # random + thr, X={2,3}
                self.assertTrue(
                    self.app.appoint_host(override_stats=mock_hosts) in
                    host_list[1:3]
                )
            elif isinstance(correct_results[index], str):
                self.assertEqual(
                    self.app.appoint_host(override_stats=mock_hosts),
                    correct_results[index]
                )
            else:
                self.assertRaises(
                    correct_results[index],
                    self.app.appoint_host,
                    override_stats=mock_hosts
                )


def _process_host(host, cmd):
    """Run 'get-host-metrics' on a host and return the extracted metric.

       NB: this must lie outside HostAppointer for multiprocessing to work."""
    host_alias = host
    try:
        host_fqdn = get_fqdn_by_host(host)
        if host_fqdn == get_fqdn_by_host('localhost'):
            host_alias = None
    except socket.gaierror:
        # no such host: don't consider for 'good' hosts, i.e. 'pass'.
        sys.stderr.write("Invalid host '%s'." % host)
    process = remote_cylc_cmd(cmd, capture=True, host=host_alias)
    metric = process.communicate()[0]
    process.wait()
    ret_code = process.returncode
    if ret_code:
        # Can't access data => designate as 'bad' host & ignore ('pass');
        # don't raise an exception, just print to error log.
        sys.stderr.write("Can't obtain metric data from host " +
                         "'%s'; return code '%s' from '%s'\n" % (
                host, ret_code, cmd))
    else:
        return json.loads(metric)


def _process_host_unpack(args):
    """Enable multiple argument pass to multiprocess Pool for _process_host."""
    return _process_host(*args)


if __name__ == "__main__":

    def process_pool(number_processes, function, *args):
        """Generic muliprocessing Pool, which must lie within main()."""
        proc_poll = Pool(number_processes)
        result = proc_poll.map(function, *args)
        return result

    unittest.main()
