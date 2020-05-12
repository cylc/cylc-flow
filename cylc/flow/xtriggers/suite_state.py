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

import os
import sqlite3

from cylc.flow.cfgspec.glbl_cfg import glbl_cfg
from cylc.flow.cycling.util import add_offset
from cylc.flow.dbstatecheck import CylcSuiteDBChecker
from cylc.flow.platform_lookup import forward_lookup
from metomi.isodatetime.parsers import TimePointParser


def suite_state(suite, task, point, offset=None, status='succeeded',
                message=None, cylc_run_dir=None, debug=False):
    """Connect to a suite DB and query the requested task state.

    * Reports satisfied only if the remote suite state has been achieved.
    * Returns all suite state args to pass on to triggering tasks.

    Arguments:
        suite (str):
            The suite to interrogate.
        task (str):
            The name of the task to query.
        offset (str):
            The offset between the cycle this xtrigger is used in and the one
            it is querying for as an ISO8601 time duration.
            e.g. PT1H (one hour).
        status (str):
            The task status required for this xtrigger to be satisfied.
        message (str):
            The custom task output required for this xtrigger to be satisfied.
            .. note::

               This cannot be specified in conjunction with ``status``.

        cylc_run_dir (str):
            The directory in which the suite to interrogate.

            .. note::

               This only needs to be supplied if the suite is running in a
               different location to what is specified in the global
               configuration (usually ``~/cylc-run``).

        debug (bool):
            Flag to enable debug information.

    Returns:
        tuple: (satisfied, results)

        satisfied (bool):
            True if ``satisfied`` else ``False``.
        results (dict):
            Dictionary containing the args / kwargs which were provided
            to this xtrigger (except ``debug``).

    """
    cylc_run_dir = os.path.expandvars(
        os.path.expanduser(
            cylc_run_dir or forward_lookup()['run directory']
        )
    )
    if offset is not None:
        point = str(add_offset(point, offset))
    try:
        checker = CylcSuiteDBChecker(cylc_run_dir, suite)
    except (OSError, sqlite3.Error):
        # Failed to connect to DB; target suite may not be started.
        return (False, None)
    fmt = checker.get_remote_point_format()
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
    return satisfied, results
