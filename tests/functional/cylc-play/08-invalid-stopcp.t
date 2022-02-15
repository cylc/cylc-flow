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

# Ensure that the Scheduler is able to run in profile mode without falling
# over. It should produce a profile file at the end.

. "$(dirname "$0")/test_header"

set_test_number 4

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    initial cycle point = 1066
    [[graph]]
        R1 = foo
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

# Assert malformed stopcp causes failure:
run_fail "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" --no-detach --stopcp potato

grep_ok "UserInputError: Invalid stop cyclepoint (stopcp): potato" \
    "${TEST_NAME_BASE}-run.stderr"

# Check that we haven't got a database ready which appears corrupted:
run_ok "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" --no-detach

purge
