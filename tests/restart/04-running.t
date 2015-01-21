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
# Test restarting a simple suite with a running task
if [[ -z ${TEST_DIR:-} ]]; then
    . $(dirname $0)/test_header
fi
#-------------------------------------------------------------------------------
set_test_number 13
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE running
TEST_SUITE_RUN_OPTIONS=
SUITE_TIMEOUT=240
if [[ -n ${CYLC_TEST_BATCH_TASK_HOST:-} && ${CYLC_TEST_BATCH_TASK_HOST:-} != 'None' ]]; then
    ssh $CYLC_TEST_BATCH_TASK_HOST mkdir -p .cylc/$SUITE_NAME/
    scp $TEST_DIR/$SUITE_NAME/passphrase $CYLC_TEST_BATCH_TASK_HOST:.cylc/$SUITE_NAME/passphrase
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
suite_run_ok $TEST_NAME cylc run --debug $TEST_SUITE_RUN_OPTIONS $SUITE_NAME
# Sleep until penultimate task (the suite stops and starts, so port files alone
# won't help)
TEST_NAME=$TEST_NAME_BASE-monitor
START_TIME=$(date +%s)
export START_TIME SUITE_NAME SUITE_TIMEOUT
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME || ! -e $TEST_DIR/suite-stopping ]]; do
    if [[ $(date +%s) > $(( START_TIME + SUITE_TIMEOUT )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__
cmp_ok "$TEST_NAME.stderr" </dev/null
state_dir=$(cylc get-global-config --print-run-dir)/$SUITE_NAME/state/
cp $state_dir/state $TEST_DIR/
for state_file in $(ls $TEST_DIR/state*); do
    sed -i "/^time : /d" $state_file
done
cmp_ok $TEST_DIR/state-pre-restart-2013092300 <<'__STATE__'
run mode : live
initial cycle : 2013092300
final cycle : 2013092306
(dp1
.
Begin task states
force_restart.2013092300 : status=running, spawned=true
force_restart.2013092306 : status=waiting, spawned=false
output_states.2013092300 : status=waiting, spawned=false
running_task.2013092300 : status=running, spawned=true
running_task.2013092306 : status=waiting, spawned=false
tidy.2013092300 : status=waiting, spawned=false
__STATE__
grep_ok "running_task|2013092300|1|1|running" $TEST_DIR/states-db-pre-restart-2013092300
contains_ok $TEST_DIR/states-db-post-restart-2013092300 <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
running_task|2013092300|1|1|running
tidy|2013092300|0|1|waiting
__DB_DUMP__
cmp_ok $TEST_DIR/state-pre-restart-2013092306 <<'__STATE__'
run mode : live
initial cycle : 2013092300
final cycle : 2013092306
(dp1
.
Begin task states
force_restart.2013092306 : status=running, spawned=true
force_restart.2013092312 : status=held, spawned=false
output_states.2013092306 : status=waiting, spawned=false
running_task.2013092306 : status=running, spawned=true
running_task.2013092312 : status=held, spawned=false
tidy.2013092300 : status=succeeded, spawned=true
tidy.2013092306 : status=waiting, spawned=false
__STATE__
contains_ok $TEST_DIR/states-db-pre-restart-2013092306 <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|1|1|running
output_states|2013092300|1|1|succeeded
output_states|2013092306|0|1|waiting
running_task|2013092300|1|1|succeeded
running_task|2013092306|1|1|running
tidy|2013092300|1|1|succeeded
tidy|2013092306|0|1|waiting
__DB_DUMP__

contains_ok $TEST_DIR/states-db-post-restart-2013092306 <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|1|1|succeeded
output_states|2013092300|1|1|succeeded
output_states|2013092306|2|1|running
running_task|2013092300|1|1|succeeded
running_task|2013092306|1|1|succeeded
tidy|2013092300|1|1|succeeded
tidy|2013092306|0|1|waiting
__DB_DUMP__
cmp_ok $TEST_DIR/state <<'__STATE__'
run mode : live
initial cycle : 2013092300
final cycle : 2013092306
(dp1
.
Begin task states
force_restart.2013092312 : status=held, spawned=false
output_states.2013092312 : status=held, spawned=false
running_task.2013092312 : status=held, spawned=false
tidy.2013092306 : status=succeeded, spawned=true
tidy.2013092312 : status=held, spawned=false
__STATE__
sqlite3 $(cylc get-global-config --print-run-dir)/$SUITE_NAME/cylc-suite.db \
 "select name, cycle, submit_num, try_num, status
  from task_states
  order by name, cycle;" > $TEST_DIR/states-db
contains_ok $TEST_DIR/states-db <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|1|1|succeeded
output_states|2013092300|1|1|succeeded
output_states|2013092306|2|1|succeeded
running_task|2013092300|1|1|succeeded
running_task|2013092306|1|1|succeeded
tidy|2013092300|1|1|succeeded
tidy|2013092306|1|1|succeeded
__DB_DUMP__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
if [[ -n ${CYLC_TEST_BATCH_TASK_HOST:-} && ${CYLC_TEST_BATCH_TASK_HOST:-} != 'None' && -n $SUITE_NAME ]]; then
    ssh $CYLC_TEST_BATCH_TASK_HOST rm -rf .cylc/$SUITE_NAME
fi
