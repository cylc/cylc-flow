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

from cylc.batch_sys_handlers.pbs_multi_cluster import *


def get_test_filter_poll_many_output():
    return [
        ("header1\nheader2\n123.localhost", ["123.localhost@localhost"]),
        (
            """header1
            header2
            12.localhost
            job123
            09.jd-01.foo.bar""",
            [
                "12.localhost@localhost",
                "job123",  # unchanged
                "09.jd-01.foo.bar@jd-01.foo.bar",
            ]
        ),
    ]


def get_test_manip_job_id():
    return [
        ("1.localhost", "1.localhost@localhost"),
        ("10000.jd-01", "10000.jd-01@jd-01"),
        ("   1077   ", "1077")  # unchanged
    ]


class TestPBSMultiCluster(unittest.TestCase):

    def test_filter_poll_many_output(self):
        """Basic tests for filter_poll_many_output."""
        for out, expected in get_test_filter_poll_many_output():
            job_ids = PBSMulticlusterHandler.filter_poll_many_output(out)
            self.assertEqual(expected, job_ids)

    def test_manip_job_id(self):
        """Basic tests for manip_job_id."""
        for job_id, expected in get_test_manip_job_id():
            mod_job_id = PBSMulticlusterHandler.manip_job_id(job_id)
            self.assertEqual(expected, mod_job_id)

    def test_export_handler(self):
        import cylc.batch_sys_handlers.pbs_multi_cluster as m
        self.assertTrue(hasattr(m, 'BATCH_SYS_HANDLER'))


if __name__ == '__main__':
    unittest.main()
