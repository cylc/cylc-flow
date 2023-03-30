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
# Test "cylc cat-log" on the workflow host.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 31
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-workflow-log-log
run_ok "${TEST_NAME}" cylc cat-log "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" "${WORKFLOW_RUN_DIR}/log/scheduler/log"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-workflow-log-fail
run_fail "${TEST_NAME}" cylc cat-log -f e "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stderr" - << __END__
InputError: The '-f' option is for job logs only.
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-out
run_ok "${TEST_NAME}" cylc cat-log -f o "${WORKFLOW_NAME}//1/a-task"
grep_ok '^the quick brown fox$' "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-job
run_ok "${TEST_NAME}" cylc cat-log -f j "${WORKFLOW_NAME}//1/a-task"
contains_ok "${TEST_NAME}.stdout" - << __END__
# SCRIPT:
# Write to task stdout log
echo "the quick brown fox"
# Write to task stderr log
echo "jumped over the lazy dog" >&2
# Write to a custom log file
echo "drugs and money" > \${CYLC_TASK_LOG_ROOT}.custom-log
# Generate a warning message in the workflow log.
cylc message -p WARNING 'marmite and squashed bananas'
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-err
run_ok "${TEST_NAME}" cylc cat-log -f e "${WORKFLOW_NAME}//1/a-task"
grep_ok "jumped over the lazy dog" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-status
run_ok "${TEST_NAME}" cylc cat-log -f s "${WORKFLOW_NAME}//1/a-task"
grep_ok "CYLC_JOB_RUNNER_NAME=background" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-activity
run_ok "${TEST_NAME}" cylc cat-log -f a "${WORKFLOW_NAME}//1/a-task"
grep_ok '\[jobs-submit ret_code\] 0' "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-custom
run_ok "${TEST_NAME}" cylc cat-log -f 'job.custom-log' "${WORKFLOW_NAME}//1/a-task"
grep_ok "drugs and money" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-list-local-NN
run_ok "${TEST_NAME}" cylc cat-log -f a -m l "${WORKFLOW_NAME}//1/a-task"
contains_ok "${TEST_NAME}.stdout" <<__END__
job
job-activity.log
job.custom-log
job.err
job.out
job.status
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-list-local-01
run_ok "${TEST_NAME}" cylc cat-log -f a -m l -s 1 "${WORKFLOW_NAME}//1/a-task"
contains_ok "${TEST_NAME}.stdout" <<__END__
job
job-activity.log
job.custom-log
job.err
job.out
job.status
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-list-local-02
run_fail cylc cat-log -f j -m l -s 2 "${WORKFLOW_NAME}//1/a-task"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-log-dir-NN
run_ok "${TEST_NAME}" cylc cat-log -f j -m d "${WORKFLOW_NAME}//1/a-task"
grep_ok "${WORKFLOW_NAME}/log/job/1/a-task/NN$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-log-dir-01
run_ok "${TEST_NAME}" cylc cat-log -f j -m d -s 1 "${WORKFLOW_NAME}//1/a-task"
grep_ok "${WORKFLOW_NAME}/log/job/1/a-task/01$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-job-path
run_ok "${TEST_NAME}" cylc cat-log -f j -m p "${WORKFLOW_NAME}//1/a-task"
grep_ok "${WORKFLOW_NAME}/log/job/1/a-task/NN/job$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
# it shouldn't let you modify the file path to access other resources
# use the dedicated options
TEST_NAME=${TEST_NAME_BASE}-un-norm-path
run_fail "${TEST_NAME}" cylc cat-log -f j/../02/j "${WORKFLOW_NAME}//1/a-task"
grep_ok 'InputError' "${TEST_NAME}.stderr"
purge
exit
