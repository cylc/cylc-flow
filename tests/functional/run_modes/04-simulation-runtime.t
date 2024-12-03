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

# Test that we can broadcast an alteration to simulation mode.

. "$(dirname "$0")/test_header"
skip_macos_gh_actions
set_test_number 7

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-start" \
    cylc play "${WORKFLOW_NAME}" --mode=simulation --pause
SCHD_LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"

# This broadcast will ensure that second_task will not finish
# in time for the workflow timeout, unless the broadcast
# cancelletion works correctly:
run_ok "second-task-broadcast-too-long" \
    cylc broadcast "${WORKFLOW_NAME}" \
        -n second_task \
        -s 'execution time limit = P1D'

poll_grep 'Broadcast set:' "${SCHD_LOG}"

# Test cancelling broadcast changes the task config back.
run_ok "cancel-second-task-broadcast" \
    cylc broadcast "${WORKFLOW_NAME}" \
        -n second_task\
        --clear

poll_grep 'Broadcast cancelled:' "${SCHD_LOG}"

# If we speed up the simulated first_task task we
# can make it finish before workflow timeout
# (neither change will do this on its own):
run_ok "first-task-speed-up-broadcast" \
    cylc broadcast "${WORKFLOW_NAME}" \
        -n first_task \
        -s '[simulation]speedup factor = 60' \
        -s 'execution time limit = PT60S'

workflow_run_ok "${TEST_NAME_BASE}-unpause" \
    cylc play "${WORKFLOW_NAME}"

# Wait for the workflow to finish (it wasn't run in no-detach mode):
poll_workflow_stopped

# If we hadn't changed the speedup factor using broadcast
# The workflow timeout would have been hit:
grep_fail "WARNING - Orphaned tasks" "${SCHD_LOG}"

purge
