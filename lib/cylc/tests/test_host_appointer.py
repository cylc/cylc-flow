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

import unittest
import json
from random import shuffle
from cylc.host_appointer import HostAppointer, EmptyHostList
from cylc.hostuserutil import get_host


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
            metric.update({'disk-space:' + self.app.USE_DISK_PATH: disk_int})
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

    def create_mock_hosts(self, n_hosts, initial_values, increments, load_var):
        """Non-test method to create list of tuples of mock hosts and metrics.
        For mock hosts, 'n_hosts' in number, create associated metrics with
        data values that are incremented to create known data variation. The
        list is shuffled to remove ordering by sequence position; name label
        numbers (lower for lower values) indicate the data ordering.
        """
        mock_host_data = []
        for label in range(1, n_hosts + 1):
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
            set_hosts = ['localhost']
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
                                self.app.USE_DISK_PATH)
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
            set_rank_method='disk-space:%s' % self.app.USE_DISK_PATH,
            set_thresholds='load:1 1000')
        self.assertEqual(
            self.app._get_host_metrics_opts(),
            set(['--disk-space=' + self.app.USE_DISK_PATH, '--load']),
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
        self.assertTrue(self.app._remove_bad_hosts().get('localhost', False))
        # Test 'localhost' true identifier is treated properly too.
        self.mock_global_config(set_hosts=[get_host()])
        self.assertTrue(self.app._remove_bad_hosts().get('localhost', False))

        self.mock_global_config(set_hosts=['localhost', 'FAKE_HOST'])
        # Check for no exceptions and 'localhost' but not 'FAKE_HOST' data
        # Difficult to unittest for specific stderr string; this is sufficient.
        self.assertTrue(self.app._remove_bad_hosts().get('localhost', False))
        self.assertTrue(self.app._remove_bad_hosts().get('FAKE_HOST', True))

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
