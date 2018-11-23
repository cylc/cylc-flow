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

import unittest

from cylc.batch_sys_handlers.pbs_multi_cluster import *


def get_test_filter_poll_many_output():
    return [
        ("ignore\nignore\n123.localhost ignored", ["123.localhost@localhost"]),
        ("\n\n#\n#\n10.samba", ["10.samba@samba"]),
        (
            """
            a
            a
            12.localhost ____ # this is ignored
            09.jd-01
            """,
            [
                "12.localhost@localhost",
                "09.jd-01@jd-01",
            ]
        ),
        ("\n\n1.localhost", [])
    ]


def get_test_filter_poll_many_output_invalid():
    return [
        # could not find a `.`
        ("a\nb\nnot_an_id", ValueError)
    ]


def get_test_manip_job_id():
    return [
        ("1.localhost", "1.localhost@localhost"),
        ("10000.jd-01", "10000.jd-01@jd-01")
    ]


def get_test_manip_job_id_invalid():
    return [
        # could not find a `.`
        ("103", ValueError)
    ]


class TestPBSMultiCluster(unittest.TestCase):

    def test_filter_poll_many_output(self):
        """Basic tests for filter_poll_many_output."""
        for out, expected in get_test_filter_poll_many_output():
            job_ids = PBSMulticlusterHandler.filter_poll_many_output(out)
            self.assertEqual(expected, job_ids)

    def test_filter_poll_many_output_invalid(self):
        """Test filter_poll_many_output with invalid values."""
        for out, ex in get_test_filter_poll_many_output_invalid():
            with self.assertRaises(ex):
                PBSMulticlusterHandler.filter_poll_many_output(out)

    def test_manip_job_id(self):
        """Basic tests for manip_job_id."""
        for job_id, expected in get_test_manip_job_id():
            mod_job_id = PBSMulticlusterHandler.manip_job_id(job_id)
            self.assertEqual(expected, mod_job_id)

    def test_manip_job_id_invalid(self):
        """Basic tests for manip_job_id with invalid values."""
        for job_id, ex in get_test_manip_job_id_invalid():
            with self.assertRaises(ex):
                PBSMulticlusterHandler.manip_job_id(job_id)

    def test_export_handler(self):
        import cylc.batch_sys_handlers.pbs_multi_cluster as m
        self.assertTrue(hasattr(m, 'BATCH_SYS_HANDLER'))


if __name__ == '__main__':
    unittest.main()
