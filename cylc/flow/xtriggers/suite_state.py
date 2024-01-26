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
    '''The suite_state xtrigger was renamed to workflow_state,
    this breaks Cylc 7-8 interoperability.
    This suite_state xtrigger replicates
    workflow_state - ensuring back-support'''
    return workflow_state(
        workflow=suite,
        task=task,
        point=point,
        offset=offset,
        status=status,
        message=message,
        cylc_run_dir=cylc_run_dir
    )
