#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------

# Test the submitted and submit-failed triggers work correctly in back-compat
# mode. See https://github.com/cylc/cylc-flow/issues/5771

. "$(dirname "$0")/test_header"
set_test_number 4

init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S

[scheduling]
    [[graph]]
        R1 = """
            a
            b
        """

[runtime]
    [[a]]  # should complete
    [[b]]  # should not complete
        platform = broken
__FLOW__

mv "$WORKFLOW_RUN_DIR/flow.cylc" "$WORKFLOW_RUN_DIR/suite.rc"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" --no-detach

grep_workflow_log_ok \
    "${TEST_NAME_BASE}-back-compat" \
    'Backward compatibility mode ON'
grep_workflow_log_ok \
    "${TEST_NAME_BASE}-a-complete" \
    '\[1/a running job:01 flows:1\] => succeeded'
grep_workflow_log_ok \
    "${TEST_NAME_BASE}-b-incomplete" \
    "1/b did not complete required outputs: \['submitted', 'succeeded'\]"

purge
