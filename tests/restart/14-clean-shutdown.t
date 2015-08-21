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
# Test restarting a suite with a non-now shutdown for a running task.
if [[ -z ${TEST_DIR:-} ]]; then
    . $(dirname $0)/test_header
fi
#-------------------------------------------------------------------------------
set_test_number 9
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE clean-shutdown
TEST_SUITE_RUN_OPTIONS=
SUITE_TIMEOUT=240
if [[ -n ${CYLC_TEST_BATCH_TASK_HOST:-} && ${CYLC_TEST_BATCH_TASK_HOST:-} != 'None' ]]
then
    ssh ${SSH_OPTS} -n "${CYLC_TEST_BATCH_TASK_HOST}" \
        "mkdir -p '.cylc/${SUITE_NAME}/'"
    scp ${SSH_OPTS} "${TEST_DIR}/${SUITE_NAME}/passphrase" \
        "${CYLC_TEST_BATCH_TASK_HOST}:.cylc/${SUITE_NAME}/passphrase"
    export CYLC_TEST_BATCH_SITE_DIRECTIVES CYLC_TEST_BATCH_TASK_HOST
    TEST_SUITE_RUN_OPTIONS="--set=BATCH_SYS_NAME=$BATCH_SYS_NAME"
    SUITE_TIMEOUT=900
fi
export TEST_DIR
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $TEST_SUITE_RUN_OPTIONS $SUITE_NAME
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --no-detach $TEST_SUITE_RUN_OPTIONS $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-restarted-run
run_ok $TEST_NAME cylc restart --no-detach $SUITE_NAME
#-------------------------------------------------------------------------------
state_dir=$(cylc get-global-config --print-run-dir)/$SUITE_NAME/state/
cp $state_dir/state $TEST_DIR/
for state_file in $(ls $TEST_DIR/*state*); do
    sed -i "/^time : /d" $state_file
done
#-------------------------------------------------------------------------------
cmp_ok $TEST_DIR/pre-restart-state <<'__STATE__'
run mode : live
initial cycle : 20130923T0000Z
final cycle : 20130923T0000Z
(dp1
.
Begin task states
finish.20130923T0000Z : status=waiting, spawned=false
output_states.20130923T0000Z : status=waiting, spawned=false
running_task.20130923T0000Z : status=running, spawned=true
__STATE__
grep_ok "running_task|20130923T0000Z|1|1|running" \
    $TEST_DIR/pre-restart-db
contains_ok $TEST_DIR/post-restart-db <<'__DB_DUMP__'
finish|20130923T0000Z|0|1|waiting
running_task|20130923T0000Z|1|1|succeeded
shutdown|20130923T0000Z|1|1|succeeded
__DB_DUMP__
sqlite3 $(cylc get-global-config --print-run-dir)/$SUITE_NAME/cylc-suite.db \
 "select name, cycle, submit_num, try_num, status
  from task_states
  order by name, cycle;" > $TEST_DIR/db
# output_states has a submit number of 2, erroneously - see #1580.
contains_ok $TEST_DIR/db <<'__DB_DUMP__'
finish|20130923T0000Z|1|1|succeeded
output_states|20130923T0000Z|2|1|succeeded
running_task|20130923T0000Z|1|1|succeeded
shutdown|20130923T0000Z|1|1|succeeded
__DB_DUMP__
cmp_ok $TEST_DIR/state <<'__STATE__'
run mode : live
initial cycle : 20130923T0000Z
final cycle : 20130923T0000Z
(dp1
.
Begin task states
finish.20130923T0000Z : status=succeeded, spawned=true
output_states.20130923T0000Z : status=succeeded, spawned=true
running_task.20130923T0000Z : status=succeeded, spawned=true
shutdown.20130923T0000Z : status=succeeded, spawned=true
__STATE__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
