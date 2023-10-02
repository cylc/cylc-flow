#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
import mock
from cylc.task_events_mgr import TaskEventsManager
from cylc.subprocctx import SubProcContext


class TestTaskEventsManager(unittest.TestCase):

    @mock.patch("cylc.task_events_mgr.LOG")
    def test_log_error_on_error_exit_code(self, cylc_log):
        """Test that an error log is emitted when the log retrieval command
        exited with a code different than zero.

        :param cylc_log: mocked cylc logger
        :type cylc_log: mock.MagicMock
        """
        task_events_manager = TaskEventsManager(None, None, None, None)
        proc_ctx = SubProcContext(cmd_key=None, cmd="error", ret_code=1,
                                  err="Error!", id_keys=[])
        task_events_manager._job_logs_retrieval_callback(proc_ctx, None)
        self.assertEqual(1, cylc_log.error.call_count)
        self.assertTrue(cylc_log.error.call_args.contains("Error!"))

    @mock.patch("cylc.task_events_mgr.LOG")
    def test_log_debug_on_noerror_exit_code(self, cylc_log):
        """Test that a debug log is emitted when the log retrieval command
        exited with an non-error code (i.e. 0).

        :param cylc_log: mocked cylc logger
        :type cylc_log: mock.MagicMock
        """
        task_events_manager = TaskEventsManager(None, None, None, None)
        proc_ctx = SubProcContext(cmd_key=None, cmd="ls /tmp/123", ret_code=0,
                                  err="", id_keys=[])
        task_events_manager._job_logs_retrieval_callback(proc_ctx, None)
        self.assertEqual(1, cylc_log.debug.call_count)
        self.assertTrue(cylc_log.debug.call_args.contains("ls /tmp/123"))

    def test_execution_polling_delays(self):
        delays = []
        time_limit_delays = [20, 30]
        time_limit = 30
        result = TaskEventsManager(
            None, None, None, None
        ).process_execution_polling_delays(
            delays, time_limit_delays, time_limit
        )
        assert result == [50, 60]


if __name__ == '__main__':
    unittest.main()
