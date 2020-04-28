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
"""Run reference test."""

from difflib import unified_diff
import re


from cylc.flow import LOG
from cylc.flow.exceptions import SuiteEventError
from cylc.flow.pathutil import get_suite_test_log_name


def run_reftest(config, ctx):
    """Run reference test at shutdown."""
    reffilename = config.get_ref_log_name()
    curfilename = get_suite_test_log_name(ctx.suite)
    ref = _load_reflog(reffilename)
    cur = _load_reflog(curfilename)
    if ref == cur:
        LOG.info('SUITE REFERENCE TEST PASSED')
    else:
        exc = SuiteEventError(
            'SUITE REFERENCE TEST FAILED\n'
            'triggering is NOT consistent with the reference log:\n%s\n'
            % '\n'.join(unified_diff(ref, cur, 'reference', 'this run'))
        )
        LOG.exception(exc)
        raise exc


def _load_reflog(filename):
    """Reference test: get trigger info from reference log."""
    res = []
    re_trig = re.compile(r'(\[.+\]\s-triggered\soff\s\[.+\])$')
    for line in open(filename, 'r'):
        match = re_trig.search(line)
        if match:
            res.append(match.groups()[0])
    res.sort()
    return res
