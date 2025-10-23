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

# ``cylc stop --kill`` kills running tasks before shutting down the scheduler

. "$(dirname "$0")/test_header"

set_test_number 4

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    initial cycle point = 1
    cycling mode = integer
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = """
            cylc stop --kill "$CYLC_WORKFLOW_ID"
            sleep 60  # if the stop --kill fails then the job succeeds
        """
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

run_ok "${TEST_NAME_BASE}" cylc play --no-detach "${WORKFLOW_NAME}" --debug

WORKFLOW_LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"

named_grep_ok \
    "${TEST_NAME_BASE}-jobs-kill-succeeded" \
    "jobs-kill ret_code\] 0" \
    "${WORKFLOW_LOG}"
named_grep_ok \
    "${TEST_NAME_BASE}-killed-foo" \
    "jobs-kill out.*1/foo/01" \
    "${WORKFLOW_LOG}"

purge
