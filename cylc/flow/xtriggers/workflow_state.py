# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

import sqlite3
from typing import Dict, Optional, Tuple

from metomi.isodatetime.parsers import TimePointParser

from cylc.flow.cycling.util import add_offset
from cylc.flow.dbstatecheck import CylcWorkflowDBChecker
from cylc.flow.pathutil import expand_path, get_cylc_run_dir
from cylc.flow.id_cli import parse_id


def workflow_state(
    workflow: str,
    task: str,
    point: str,
    offset: Optional[str] = None,
    status: str = 'succeeded',
    message: Optional[str] = None,
    cylc_run_dir: Optional[str] = None
) -> Tuple[bool, Optional[Dict[str, Optional[str]]]]:
    """Connect to a workflow DB and query the requested task state.

    * Reports satisfied only if the remote workflow state has been achieved.
    * Returns all workflow state args to pass on to triggering tasks.

    Arguments:
        workflow:
            The workflow to interrogate.
        task:
            The name of the task to query.
        point:
            The cycle point.
        offset:
            The offset between the cycle this xtrigger is used in and the one
            it is querying for as an ISO8601 time duration.
            e.g. PT1H (one hour).
        status:
            The task status required for this xtrigger to be satisfied.
        message:
            The custom task output required for this xtrigger to be satisfied.
            .. note::

               This cannot be specified in conjunction with ``status``.
        cylc_run_dir:
            Alternate cylc-run directory, e.g. for another user.

            .. note::

               This only needs to be supplied if the workflow is running in a
               different location to what is specified in the global
               configuration (usually ``~/cylc-run``).

    Returns:
        tuple: (satisfied, results)

        satisfied:
            True if ``satisfied`` else ``False``.
        results:
            Dictionary containing the args / kwargs which were provided
            to this xtrigger.

    """
    if cylc_run_dir:
        run_dir = cylc_run_dir = expand_path(cylc_run_dir)
    else:
        cylc_run_dir = get_cylc_run_dir()
        run_dir = None

    # This infers the latest run number.
    workflow, *_ = parse_id(
        workflow,
        constraint='workflows',
        alt_run_dir=run_dir
    )

    if offset is not None:
        point = str(add_offset(point, offset))

    try:
        checker = CylcWorkflowDBChecker(cylc_run_dir, workflow)
    except (OSError, sqlite3.Error):
        # Failed to connect to DB; target workflow may not be started.
        return (False, None)
    try:
        fmt = checker.get_remote_point_format()
    except sqlite3.OperationalError as exc:
        try:
            fmt = checker.get_remote_point_format_compat()
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
        'workflow': workflow,
        'task': task,
        'point': point,
        'offset': offset,
        'status': status,
        'message': message,
        'cylc_run_dir': cylc_run_dir
    }
    return satisfied, results
