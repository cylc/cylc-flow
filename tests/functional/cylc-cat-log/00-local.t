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
set_test_number 43
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --no-detach "${WORKFLOW_NAME}" --reference-test
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-workflow-log-log
run_ok "${TEST_NAME}" cylc cat-log "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" "${WORKFLOW_RUN_DIR}/log/scheduler/log"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-workflow-log-ok
LOG_DIR="$(dirname "$(cylc cat-log -m p "${WORKFLOW_NAME}")")"
echo "This is file 02-restart-02.log" > "${LOG_DIR}/02-restart-02.log"
echo "This is file 03-restart-02.log" > "${LOG_DIR}/03-restart-02.log"
# it should accept file paths relative to the scheduler log directory
run_ok "${TEST_NAME}" cylc cat-log -f scheduler/03-restart-02.log "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" - << __END__
This is file 03-restart-02.log
__END__
# it should pick the latest scheduler log file if no rotation number is provided
run_ok "${TEST_NAME}" cylc cat-log --file s "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" - << __END__
This is file 03-restart-02.log
__END__
# it should apply rotation number to scheduler log files
run_ok "${TEST_NAME}" cylc cat-log -f s -r 1 "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME}.stdout" - << __END__
This is file 02-restart-02.log
__END__
# it should list scheduler log files
run_ok "${TEST_NAME}" cylc cat-log -m l "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - << __END__
config/01-start-01.cylc
config/flow-processed.cylc
install/01-install.log
scheduler/01-start-01.log
scheduler/02-restart-02.log
scheduler/03-restart-02.log
scheduler/reftest.log
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
echo "drugs, money & whitespace" > "\${CYLC_TASK_LOG_ROOT} custom.log"
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
run_ok "${TEST_NAME}" cylc cat-log -f 'job custom.log' "${WORKFLOW_NAME}//1/a-task"
grep_ok "drugs, money & whitespace" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-list-local-NN
run_ok "${TEST_NAME}" cylc cat-log -f a -m l "${WORKFLOW_NAME}//1/a-task"
contains_ok "${TEST_NAME}.stdout" <<__END__
job
job-activity.log
job custom.log
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
job custom.log
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
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-prepend-path
run_ok "${TEST_NAME}-get-path" cylc cat-log -m p "${WORKFLOW_NAME}//1/a-task"
run_ok "${TEST_NAME}" cylc cat-log --prepend-path "${WORKFLOW_NAME}//1/a-task"
grep_ok "$(cat "#.*${TEST_NAME}-get-path.stdout")" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-submit-failed
run_ok "${TEST_NAME}" cylc cat-log -m l "${WORKFLOW_NAME}//1/submit-failed"
contains_ok "${TEST_NAME}.stdout" <<__END__
job.tmp
job-activity.log
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-list-no-install-dir
rm -r "${WORKFLOW_RUN_DIR}/log/install"
run_ok "${TEST_NAME}-get-path" cylc cat-log -m l "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
purge
exit
