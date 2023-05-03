#!/bin/bash
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

# GitHub 5231: Test that a finished workflow waits on a timeout if restarted.

. "$(dirname "$0")/test_header"

set_test_number 8

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

TEST_NAME="${TEST_NAME_BASE}-val"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

# Run to completion.
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach "${WORKFLOW_NAME}"

# Restart completed workflow: it should stall on a restart timer.
TEST_NAME="${TEST_NAME_BASE}-restart"
run_ok "${TEST_NAME}" cylc play "${WORKFLOW_NAME}"

# Search log for restart timer.
TEST_NAME="${TEST_NAME_BASE}-grep1"
grep_workflow_log_ok "${TEST_NAME}" "restart timer starts NOW"

# Check that it has not shut down automatically.
TEST_NAME="${TEST_NAME_BASE}-grep2"
grep_fail "Workflow shutting down" "${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Retriggering the task should stop the timer, and shut down as complete again.
TEST_NAME="${TEST_NAME_BASE}-trigger"
run_ok "${TEST_NAME}" cylc trigger "${WORKFLOW_NAME}//1/foo"

poll_grep_workflow_log "Workflow shutting down - AUTOMATIC"

TEST_NAME="${TEST_NAME_BASE}-grep3"
grep_workflow_log_ok "${TEST_NAME}" "restart timer stopped"

# It should not be running now.
TEST_NAME="${TEST_NAME_BASE}-ping"
run_fail "${TEST_NAME}" cylc ping "${WORKFLOW_NAME}"

purge
