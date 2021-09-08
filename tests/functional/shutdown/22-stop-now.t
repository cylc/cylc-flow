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

set_test_number 3

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    initial cycle point = 1
    cycling mode = integer
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = """
            # Infinite loop:
            while true; do sleep 10; done
        """
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

cylc play "${WORKFLOW_NAME}"

WORKFLOW_LOG="${WORKFLOW_RUN_DIR}/log/workflow/log"

waitfor() {
    # Takes a regex and waits for it to appear in log. Times out after 10
    # seconds.
    counter=0
    # shellcheck disable=SC2143
    while [[ $(grep -q "${1}" "${WORKFLOW_LOG}") && "${counter}" -lt 10 ]]; do
        sleep 1
        counter=$(( counter + 1 ))
    done
}

# Wait for foo to start:
waitfor "foo.1.*started"

run_ok "${TEST_NAME_BASE}" cylc stop --now "${WORKFLOW_NAME}"

# Wait for scheduler to stop:
waitfor "INFO - DONE"

grep_ok 'Orphaned task jobs.*\n.*foo.1' "${WORKFLOW_LOG}" -Pz

purge
