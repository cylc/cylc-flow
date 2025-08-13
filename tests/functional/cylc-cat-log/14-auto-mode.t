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
# Test "cylc cat-log" using auto mode with a custom tail /command
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
create_test_global_config "" "
[platforms]
   [[localhost]]
        tail command template = $PWD/bin/my-tailer.sh %(filename)s
"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"
cylc workflow-state "${WORKFLOW_NAME}//1/foo:started" --interval=1
sleep 3
# Test that the custom tail command is used when the task is live
TEST_NAME=${TEST_NAME_BASE}-cat-log-auto-tail
cylc cat-log "${WORKFLOW_NAME}//1/foo" -f o -m a > "${TEST_NAME}.out"
grep_ok "HELLO from foo 1" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
cylc stop --kill --max-polls=20 --interval=1 "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# Test that the custom tail command is not used when the task is not live
# (i.e., auto mode should not use the custom tail command)
TEST_NAME=${TEST_NAME_BASE}-cat-log-auto-cat
cylc cat-log "${WORKFLOW_NAME}//1/foo" -f o -m a > "${TEST_NAME}.out"
grep_fail "HELLO from foo 1" "${TEST_NAME}.out"
grep_ok "from foo 1" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
# Test that the custom tail command is not used when workflow logs are requested
# (i.e., auto mode should not use the custom tail command)
TEST_NAME=${TEST_NAME_BASE}-cat-log-auto-workflow
# Use the workflow name without the task ID to get the workflow logs
cylc cat-log "${WORKFLOW_NAME}" -m a > "${TEST_NAME}.out"
grep_fail "HELLO" "${TEST_NAME}.out"
grep_ok "Workflow:.*/functional/cylc-cat-log/14-auto-mode" "${TEST_NAME}.out"
purge
