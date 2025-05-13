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

# GitHub 5067: if a task is removed from the graph after shutdown, it should not
# cause an error at restart. If it was a failed incomplete task, however, it
# should still be polled and logged at restart.

. "$(dirname "$0")/test_header"

set_test_number 7

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate --set="INCL_B_C=True" "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate --set="INCL_B_C=False" "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach "${WORKFLOW_NAME}"

# Restart with removed tasks should not cause an error.
# It should shut down cleanly after orphaned task a and incomplete failed task
# b are polled (even though b has been removed from the graph) and a finishes
# (after checking the poll results).
TEST_NAME="${TEST_NAME_BASE}-restart"
workflow_run_ok "${TEST_NAME}" cylc play --set="INCL_B_C=False" --no-detach "${WORKFLOW_NAME}"

grep_workflow_log_ok "grep-3" "\[1/a/01.*\] (polled)started"
grep_workflow_log_ok "grep-4" "\[1/b/01.*\] (polled)failed"

# Failed (but not incomplete) task c should not have been polled.
grep_fail "\[1/c/01:failed\] (polled)failed" "${WORKFLOW_RUN_DIR}/log/scheduler/log"

purge
