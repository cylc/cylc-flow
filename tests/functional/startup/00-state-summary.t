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
# Test that the state summary updates immediately on start-up.
# See https://github.com/cylc/cylc-flow/pull/1756
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# Workflow runs and shuts down with a failed task.
cylc play --no-detach "${WORKFLOW_NAME}" > /dev/null 2>&1
# Restart with a failed task and a succeeded task.
cylc play "${WORKFLOW_NAME}"
poll_grep_workflow_log -E '1/foo.* \(polled\)failed'
cylc dump "${WORKFLOW_NAME}" > dump.out
TEST_NAME=${TEST_NAME_BASE}-grep
# State summary should not just say "Initializing..."
grep_ok "state totals={'waiting': 0, 'expired': 0, 'preparing': 0, 'submit-failed': 0, 'submitted': 0, 'running': 0, 'failed': 1, 'succeeded': 0}" dump.out
#-------------------------------------------------------------------------------
cylc stop --max-polls=10 --interval=2 "${WORKFLOW_NAME}"
purge
