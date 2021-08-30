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
# Test that a user script can have its own TERM signal trap.

. "$(dirname "$0")/test_header"
set_test_number 5

init_workflow "${TEST_NAME_BASE}" <<'__WORKFLOW__'
[cylc]
    [[events]]
        abort on inactivity timeout = True
        abort on stall = True
        inactivity timeout = PT1M
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = """
# ignore TERM signal for the next child
trap "" TERM
(
    cylc__job__poll_grep_workflow_log "Workflow shutting down"
    sleep 5
    echo "The undead child shall speak" >>"${CYLC_TASK_LOG_ROOT}.testout"
) &
trap "echo 'TERM got trapped' >>'${CYLC_TASK_LOG_ROOT}.testout'; wait" TERM
# this child will be terminated if job script is a process leader
(
    sleep 15
    echo "You shall never see this" >>"${CYLC_TASK_LOG_ROOT}.testout"
) &
echo "Here we go..." >>"${CYLC_TASK_LOG_ROOT}.testout"
wait
"""
        err-script = """
wait
echo "Exit with code ${CYLC_TASK_USER_SCRIPT_EXITCODE:-unknown}" \
    >>"${CYLC_TASK_LOG_ROOT}.testout"
"""
__WORKFLOW__


run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
# Needs to be detaching:
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"

JOB_LOG_ROOT="${WORKFLOW_RUN_DIR}/log/job/1/foo/01/job"

# Kill the job and see what happened
poll_grep "CYLC_JOB_PID=" "${JOB_LOG_ROOT}.status"
JOB_PID=$(awk -F= '/CYLC_JOB_PID=/{print $2}' "${JOB_LOG_ROOT}.status")
kill -s "TERM" "${JOB_PID}"
poll_workflow_stopped

# Workflow is down after failed message
grep_ok "CYLC_JOB_EXIT=TERM" "${JOB_LOG_ROOT}.status"

# The job should be still running and waiting for the user script
grep_fail "The undead child shall speak" "${JOB_LOG_ROOT}.testout"

poll_grep "Exit with code" "${JOB_LOG_ROOT}.testout"
cmp_ok "${JOB_LOG_ROOT}.testout" - <<__EOF__
Here we go...
TERM got trapped
The undead child shall speak
Exit with code 143
__EOF__

purge
exit
