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
# Test "cylc cat-log" for remote tasks.
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
create_test_global_config "" "
[platforms]
   [[${CYLC_TEST_PLATFORM}]]
       retrieve job logs = False"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play --debug --no-detach \
        -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-job
cylc cat-log -f j "${WORKFLOW_NAME}//1/a-task" >"${TEST_NAME}.out"
contains_ok "${TEST_NAME}.out" - << __END__
# SCRIPT:
# Write to task stdout log
echo "the quick brown fox"
# Write to task stderr log
echo "jumped over the lazy dog" >&2
# Write to a custom log file
echo "drugs and money" > \${CYLC_TASK_LOG_ROOT}.custom-log
__END__
#-------------------------------------------------------------------------------
# remote
TEST_NAME=${TEST_NAME_BASE}-no_log_remote
cylc cat-log -f j "${WORKFLOW_NAME}//1/a-task" >"${TEST_NAME}.out"
grep_ok "${WORKFLOW_NAME}/log/job/1/a-task/NN/job$" "${TEST_NAME}.out"
#-------------------------------------------------------------------------------
# Clean up the task host.
purge
exit
