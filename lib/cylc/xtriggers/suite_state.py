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

"""xtrigger function to check a remote suite state.

"""

import os
import sqlite3
from cylc.cycling.util import add_offset
from cylc.cfgspec.glbl_cfg import glbl_cfg
from cylc.dbstatecheck import CylcSuiteDBChecker
from isodatetime.parsers import TimePointParser


def suite_state(suite, task, point, offset=None, status='succeeded',
                message=None, cylc_run_dir=None, debug=False):
    """Connect to a suite DB and query the requested task state.

    Reports satisfied only if the remote suite state has been achieved.
    Returns all suite state args to pass on to triggering tasks.

    """
    cylc_run_dir = os.path.expandvars(
        os.path.expanduser(
            cylc_run_dir or glbl_cfg().get_host_item('run directory')))
    if offset is not None:
        point = str(add_offset(point, offset))
    try:
        checker = CylcSuiteDBChecker(cylc_run_dir, suite)
    except (OSError, sqlite3.Error):
        # Failed to connect to DB; target suite may not be started.
        return (False, None)

    try:
        fmt = checker.get_remote_point_format()
    except sqlite3.OperationalError as exc:
        try:
            fmt = checker.get_remote_point_format_forward_compat()
        except sqlite3.OperationalError:
            raise exc  # original error

    if fmt:
        my_parser = TimePointParser()
        point = str(my_parser.parse(point, dump_format=fmt))
    if message is not None:
        satisfied = checker.task_state_met(task, point, message=message)
    else:
        satisfied = checker.task_state_met(task, point, status=status)
    results = {
        'suite': suite,
        'task': task,
        'point': point,
        'offset': offset,
        'status': status,
        'message': message,
        'cylc_run_dir': cylc_run_dir
    }
    return (satisfied, results)
