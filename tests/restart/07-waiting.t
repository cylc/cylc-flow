#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
#C: Test restarting a simple suite with a waiting task
if [[ -z ${TEST_DIR:-} ]]; then
    . $(dirname $0)/test_header
fi
#-------------------------------------------------------------------------------
set_test_number 13
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE waiting
TEST_SUITE_RUN_OPTIONS=
if [[ -n ${CYLC_LL_TEST_TASK_HOST:-} && ${CYLC_LL_TEST_TASK_HOST:-} != 'None' ]]; then
    ssh $CYLC_LL_TEST_TASK_HOST mkdir -p .cylc/$SUITE_NAME/
    scp $TEST_DIR/$SUITE_NAME/passphrase $CYLC_LL_TEST_TASK_HOST:.cylc/$SUITE_NAME/passphrase
    export CYLC_LL_TEST_SITE_DIRECTIVES CYLC_LL_TEST_TASK_HOST
    TEST_SUITE_RUN_OPTIONS="--set=USE_LOADLEVELER=true"
fi
export TEST_DIR
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --debug $TEST_SUITE_RUN_OPTIONS $SUITE_NAME
# Sleep until penultimate task (the suite stops and starts, so port files alone
# won't help)
TEST_NAME=$TEST_NAME_BASE-monitor
START_TIME=$(date +%s)
export START_TIME SUITE_NAME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME || ! -e $TEST_DIR/suite-stopping ]]; do
    if [[ $(date +%s) > $(( START_TIME + 240 )) ]]; then
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
    sed -i "/^suite time : /d" $state_file
done
cmp_ok $TEST_DIR/state-pre-restart-2013092300 <<'__STATE__'
initial cycle : 2013092300
final cycle : 2013092306
(dp1
.
Begin task states
force_restart.2013092300 : status=running, spawned=true
force_restart.2013092306 : status=runahead, spawned=false
output_states.2013092300 : status=waiting, spawned=false
tidy.2013092300 : status=waiting, spawned=false
waiting_task.2013092300 : status=waiting, spawned=false
__STATE__
cmp_ok $TEST_DIR/states-db-pre-restart-2013092300 <<'__DB_DUMP__'
force_restart|2013092300|1|1|running
force_restart|2013092306|0|1|runahead
output_states|2013092300|0|1|waiting
tidy|2013092300|0|1|waiting
waiting_task|2013092300|0|1|waiting
__DB_DUMP__
cmp_ok $TEST_DIR/states-db-post-restart-2013092300 <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|0|1|runahead
output_states|2013092300|1|1|running
output_states|2013092306|0|1|runahead
tidy|2013092300|0|1|waiting
waiting_task|2013092300|0|1|waiting
__DB_DUMP__
cmp_ok $TEST_DIR/state-pre-restart-2013092306 <<'__STATE__'
initial cycle : 2013092300
final cycle : 2013092306
(dp1
.
Begin task states
force_restart.2013092306 : status=running, spawned=true
force_restart.2013092312 : status=held, spawned=false
output_states.2013092306 : status=waiting, spawned=false
tidy.2013092300 : status=succeeded, spawned=true
tidy.2013092306 : status=waiting, spawned=false
waiting_task.2013092306 : status=waiting, spawned=false
__STATE__
cmp_ok $TEST_DIR/states-db-pre-restart-2013092306 <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|1|1|running
force_restart|2013092312|0|1|held
output_states|2013092300|1|1|succeeded
output_states|2013092306|0|1|waiting
tidy|2013092300|1|1|succeeded
tidy|2013092306|0|1|waiting
waiting_task|2013092300|1|1|succeeded
waiting_task|2013092306|0|1|waiting
__DB_DUMP__

cmp_ok $TEST_DIR/states-db-post-restart-2013092306 <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|1|1|succeeded
force_restart|2013092312|0|1|held
output_states|2013092300|1|1|succeeded
output_states|2013092306|1|1|running
output_states|2013092312|0|1|held
tidy|2013092300|1|1|succeeded
tidy|2013092306|0|1|waiting
waiting_task|2013092300|1|1|succeeded
waiting_task|2013092306|0|1|waiting
__DB_DUMP__
cmp_ok $TEST_DIR/state <<'__STATE__'
initial cycle : 2013092300
final cycle : 2013092306
(dp1
.
Begin task states
force_restart.2013092312 : status=held, spawned=false
output_states.2013092312 : status=held, spawned=false
tidy.2013092306 : status=succeeded, spawned=true
tidy.2013092312 : status=held, spawned=false
waiting_task.2013092312 : status=held, spawned=false
__STATE__
sqlite3 $(cylc get-global-config --print-run-dir)/$SUITE_NAME/cylc-suite.db \
 "select name, cycle, submit_num, try_num, status
  from task_states
  order by name, cycle;" > $TEST_DIR/states-db
cmp_ok $TEST_DIR/states-db <<'__DB_DUMP__'
force_restart|2013092300|1|1|succeeded
force_restart|2013092306|1|1|succeeded
force_restart|2013092312|0|1|held
output_states|2013092300|1|1|succeeded
output_states|2013092306|1|1|succeeded
output_states|2013092312|0|1|held
tidy|2013092300|1|1|succeeded
tidy|2013092306|1|1|succeeded
tidy|2013092312|0|1|held
waiting_task|2013092300|1|1|succeeded
waiting_task|2013092306|1|1|succeeded
waiting_task|2013092312|0|1|held
__DB_DUMP__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
if [[ -n ${CYLC_LL_TEST_TASK_HOST:-} && ${CYLC_LL_TEST_TASK_HOST:-} != 'None' && -n $SUITE_NAME ]]; then
    ssh $CYLC_LL_TEST_TASK_HOST rm -rf .cylc/$SUITE_NAME
fi
