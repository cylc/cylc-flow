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
"""Run reference test."""

from difflib import unified_diff
import re
import os


from cylc.flow import LOG
from cylc.flow.exceptions import WorkflowEventError
from cylc.flow.pathutil import get_workflow_test_log_name


RE_TRIG = re.compile(r'(.*? -triggered off \[.*\])$')


def run_reftest(config, ctx):
    """Run reference test at shutdown."""
    reffilename = config.get_ref_log_name()
    curfilename = get_workflow_test_log_name(ctx.workflow)
    ref = _load_reflog(reffilename)
    cur = _load_reflog(curfilename)
    if not ref:
        raise WorkflowEventError("No triggering events in reference log.")
    if not cur:
        raise WorkflowEventError("No triggering events in test log.")
    if ref == cur:
        LOG.info('WORKFLOW REFERENCE TEST PASSED')
    else:
        exc = WorkflowEventError(
            'WORKFLOW REFERENCE TEST FAILED\n'
            'triggering is NOT consistent with the reference log:\n%s\n'
            % '\n'.join(unified_diff(ref, cur, 'reference', 'this run'))
        )
        LOG.exception(exc)
        raise exc


def _load_reflog(filename):
    """Reference test: get trigger info from reference log."""
    res = []
    with open(os.path.expandvars(filename), 'r') as reflog:
        for line in reflog:
            match = RE_TRIG.search(line)
            if match:
                res.append(match.groups()[0])
    res.sort()
    return res
