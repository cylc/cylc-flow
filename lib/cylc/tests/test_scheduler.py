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

import logging
import unittest

from unittest import mock

from cylc import LOG
from cylc.scheduler import Scheduler


class Options(object):
    """To mimic the command line parsed options"""

    def __init__(self):
        # Variables needed to create a Scheduler instance
        self.profile_mode = False
        self.templatevars = {}
        self.templatevars_file = ""
        self.run_mode = ""


class TestScheduler(unittest.TestCase):

    @mock.patch("cylc.scheduler.BroadcastMgr")
    @mock.patch("cylc.scheduler.SuiteDatabaseManager")
    @mock.patch("cylc.scheduler.SuiteSrvFilesManager")
    def test_ioerror_is_ignored(self, mocked_suite_srv_files_mgr,
                                mocked_suite_db_mgr, mocked_broadcast_mgr):
        """Test that IOError's are ignored when closing Scheduler logs.
        When a disk errors occurs, the scheduler.close_logs method may
        result in an IOError. This, combined with other variables, may cause
        an infinite loop. So it is better that it is ignored."""
        mocked_suite_srv_files_mgr.return_value\
            .get_suite_source_dir.return_value = "."
        options = Options()
        args = ["suiteA"]
        scheduler = Scheduler(is_restart=False, options=options, args=args)

        handler = mock.MagicMock()
        handler.close.side_effect = IOError
        handler.level = logging.INFO
        LOG.addHandler(handler)

        scheduler.close_logs()
        self.assertEqual(1, handler.close.call_count)
        LOG.removeHandler(handler)


if __name__ == '__main__':
    unittest.main()
