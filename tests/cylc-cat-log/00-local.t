#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
# Test "cylc cat-log" on the suite host.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 29
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
suite_run_ok "${TEST_NAME_BASE}-run" cylc run --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-suite-log-log
run_ok "${TEST_NAME}" cylc cat-log "${SUITE_NAME}"
contains_ok "${TEST_NAME}.stdout" "${SUITE_RUN_DIR}/log/suite/log"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-suite-log-fail
run_fail "${TEST_NAME}" cylc cat-log -f e "${SUITE_NAME}"
contains_ok "${TEST_NAME}.stderr" - << __END__
UserInputError: The '-f' option is for job logs only.
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-out
run_ok "${TEST_NAME}" cylc cat-log -f o "${SUITE_NAME}" a-task.1
grep_ok '^the quick brown fox$' "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-job
run_ok "${TEST_NAME}" cylc cat-log -f j "${SUITE_NAME}" a-task.1
contains_ok "${TEST_NAME}.stdout" - << __END__
# SCRIPT:
# Write to task stdout log
echo "the quick brown fox"
# Write to task stderr log
echo "jumped over the lazy dog" >&2
# Write to a custom log file
echo "drugs and money" > \${CYLC_TASK_LOG_ROOT}.custom-log
# Generate a warning message in the suite log.
cylc task message -p WARNING 'marmite and squashed bananas'
__END__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-err
run_ok "${TEST_NAME}" cylc cat-log -f e "${SUITE_NAME}" a-task.1
grep_ok "jumped over the lazy dog" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-status
run_ok "${TEST_NAME}" cylc cat-log -f s "${SUITE_NAME}" a-task.1
grep_ok "CYLC_BATCH_SYS_NAME=background" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-activity
run_ok "${TEST_NAME}" cylc cat-log -f a "${SUITE_NAME}" a-task.1
grep_ok '\[jobs-submit ret_code\] 0' "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-custom
run_ok "${TEST_NAME}" cylc cat-log -f 'job.custom-log' "${SUITE_NAME}" a-task.1
grep_ok "drugs and money" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-list-local-NN
run_ok "${TEST_NAME}" cylc cat-log -f a -m l "${SUITE_NAME}" a-task.1
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
run_ok "${TEST_NAME}" cylc cat-log -f a -m l -s 1 "${SUITE_NAME}" a-task.1
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
run_fail cylc cat-log -f j -m l -s 2 "${SUITE_NAME}" a-task.1
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-log-dir-NN
run_ok "${TEST_NAME}" cylc cat-log -f j -m d "${SUITE_NAME}" a-task.1
grep_ok "${SUITE_NAME}/log/job/1/a-task/NN$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-log-dir-01
run_ok "${TEST_NAME}" cylc cat-log -f j -m d -s 1 "${SUITE_NAME}" a-task.1
grep_ok "${SUITE_NAME}/log/job/1/a-task/01$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-task-job-path
run_ok "${TEST_NAME}" cylc cat-log -f j -m p "${SUITE_NAME}" a-task.1
grep_ok "${SUITE_NAME}/log/job/1/a-task/NN/job$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
