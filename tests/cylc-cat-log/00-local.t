#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 17
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
# Run detached so we get suite out and err logs.
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
sleep 5
# Wait for the suite to finish.
cylc stop --max-polls=10 --interval=2 $SUITE_NAME 2>'/dev/null'
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-suite-log-log
cylc cat-log $SUITE_NAME >$TEST_NAME.out
grep_ok 'Suite starting at' $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-suite-log-out
cylc cat-log -o $SUITE_NAME >$TEST_NAME.out
grep_ok 'DONE' $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-suite-log-err
cylc cat-log -e $SUITE_NAME >$TEST_NAME.out
grep_ok 'marmite and squashed bananas' $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-out
cylc cat-log -o $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok '^the quick brown fox$' $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-job
cylc cat-log $SUITE_NAME a-task.1 >$TEST_NAME.out
contains_ok $TEST_NAME.out - << __END__
# SCRIPT:
# Write to task stdout log
echo "the quick brown fox"
# Write to task stderr log
echo "jumped over the lazy dog" >&2
# Write to a custom log file
echo "drugs and money" > \${CYLC_TASK_LOG_ROOT}.custom-log
# Generate a message in the suite err log.
cylc task message -p WARNING 'marmite and squashed bananas'
__END__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-err
cylc cat-log -e $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok "jumped over the lazy dog" $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-status
cylc cat-log -u $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok "CYLC_BATCH_SYS_NAME=background" $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-activity
cylc cat-log -a $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok '\[job-submit ret_code\] 0' $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-custom
cylc cat-log -c 'job.custom-log' $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok "drugs and money" $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-list-local-NN
cylc cat-log --list-local $SUITE_NAME a-task.1 >$TEST_NAME.out
cmp_ok $TEST_NAME.out <<__END__
job
job-activity.log
job.custom-log
job.err
job.out
job.status
__END__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-list-local-01
cylc cat-log --list-local -s 1 $SUITE_NAME a-task.1 >$TEST_NAME.out
cmp_ok $TEST_NAME.out <<__END__
job
job-activity.log
job.custom-log
job.err
job.out
job.status
__END__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-list-local-02
run_fail cylc cat-log --list-local -s 2 $SUITE_NAME a-task.1
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-log-dir-NN
cylc cat-log --list-local -l $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok "$SUITE_NAME/log/job/1/a-task/NN$" $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-log-dir-01
cylc cat-log --list-local -l -s 1 $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok "$SUITE_NAME/log/job/1/a-task/01$" $TEST_NAME.out
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-task-job-path
cylc cat-log -l $SUITE_NAME a-task.1 >$TEST_NAME.out
grep_ok "$SUITE_NAME/log/job/1/a-task/NN/job$" $TEST_NAME.out
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
