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

from cylc.flow import LOG
import cylc.flow.flags
from cylc.flow.xtriggers.workflow_state import workflow_state

if not cylc.flow.flags.cylc7_back_compat:
    LOG.warning(
        "The suite_state xtrigger is deprecated. "
        "Please use the workflow_state xtrigger instead."
    )


def suite_state(suite, task, point, offset=None, status='succeeded',
                message=None, cylc_run_dir=None, debug=False):
    """Suite state xtrigger, required for interoperability with Cylc 7.

    * The suite_state xtrigger was renamed to workflow_state, this breaks Cylc 7-8 interoperability.
    * This suite_state xtrigger replicates workflow_state - ensuring back-support.

    Arguments:
        suite:
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
            The directory in which the workflow to interrogate.

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
    return workflow_state(
        workflow=suite,
        task=task,
        point=point,
        offset=offset,
        status=status,
        message=message,
        cylc_run_dir=cylc_run_dir
    )
