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

# Test `cylc play` start up or resume under various contact scenarios:
#  - running, normally
#  - stopped, normally
#  - stopped, but orphaned contact file
#  - running, but can't be contacted

. "$(dirname "$0")/test_header"

set_test_number 10

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = false
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${WORKFLOW_NAME}"

# Not running: play should start it up.
# (run like this "(cmd &) >/dev/null" to discard the process killed message) 
(cylc play --pause --no-detach "${WORKFLOW_NAME}" \
    1>"${TEST_NAME_BASE}.out" 2>&1 &) 2>/dev/null
poll_workflow_running
poll_grep_workflow_log "Pausing the workflow: Paused on start up"

# Already running: play should resume.
TEST_NAME="${TEST_NAME_BASE}-resume"
run_ok "${TEST_NAME}" \
    cylc play "${WORKFLOW_NAME}"

grep_ok "Resuming already-running workflow" "${TEST_NAME}.stdout"
poll_grep_workflow_log "RESUMING the workflow now"

# Orphan the contact file
# Play should timeout, remove the contact file, and start up.
TEST_NAME="${TEST_NAME_BASE}-orphan"

eval "$(cylc get-workflow-contact "${WORKFLOW_NAME}" | grep CYLC_WORKFLOW_PID)"
kill -9 "${CYLC_WORKFLOW_PID}" > /dev/null 2>&1

run_ok "${TEST_NAME}" \
    cylc play "${WORKFLOW_NAME}" --comms-timeout=1 --pause
grep_ok "Connection timed out (1000.0 ms)" "${TEST_NAME}.stderr"
grep_ok "Removed contact file" "${TEST_NAME}.stderr"
poll_grep_workflow_log "Pausing the workflow: Paused on start up"

# Mess with the port: play aborts as can't tell if workflow is running or not.
# (The ping times out, then `cylc psutil` can't find the workflow).
eval "$(cylc get-workflow-contact "${WORKFLOW_NAME}" | grep CYLC_WORKFLOW_PORT)"
sed -i 's/CYLC_WORKFLOW_PORT=.*/CYLC_WORKFLOW_PORT=490001/' \
    "$WORKFLOW_RUN_DIR/.service/contact"
run_fail "${TEST_NAME}" \
    cylc play "${WORKFLOW_NAME}" --comms-timeout=1
grep_ok "Connection timed out (1000.0 ms)" "${TEST_NAME}.stderr"
grep_ok "Cannot tell if the workflow is running" "${TEST_NAME}.stderr"

# Restore contact file and shut down.
sed -i "s/CYLC_WORKFLOW_PORT=.*/CYLC_WORKFLOW_PORT=${CYLC_WORKFLOW_PORT}/" \
    "$WORKFLOW_RUN_DIR/.service/contact"
run_ok "${TEST_NAME}" \
    cylc stop --now "${WORKFLOW_NAME}"

purge
