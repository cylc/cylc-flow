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
# Test restarting a suite with multi-cycle tasks and interdependencies.
if [[ -z ${TEST_DIR:-} ]]; then
    . $(dirname $0)/test_header
fi
#-------------------------------------------------------------------------------
set_test_number 9
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE multicycle
export TEST_DIR
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-restart-run
suite_run_ok $TEST_NAME cylc restart --debug $SUITE_NAME
#-------------------------------------------------------------------------------
state_dir=$(cylc get-global-config --print-run-dir)/$SUITE_NAME/state/
cp $state_dir/state $TEST_DIR/
for state_file in $(ls $TEST_DIR/*state*); do
    sed -i "/^time : /d" $state_file
done
cmp_ok $TEST_DIR/pre-restart-state <<'__STATE__'
run mode : live
initial cycle : 20130923T0000Z
final cycle : 20130926T0000Z
(dp1
.
Begin task states
bar.20130924T0000Z : status=succeeded, spawned=true
bar.20130924T1200Z : status=succeeded, spawned=true
bar.20130925T0000Z : status=waiting, spawned=false
foo.20130924T1200Z : status=succeeded, spawned=true
foo.20130925T0000Z : status=waiting, spawned=false
output_states.20130925T0000Z : status=waiting, spawned=false
__STATE__
cmp_ok $TEST_DIR/pre-restart-db <<'__DB_DUMP__'
bar|20130923T0000Z|1|1|succeeded
bar|20130923T1200Z|1|1|succeeded
bar|20130924T0000Z|1|1|succeeded
bar|20130924T1200Z|1|1|succeeded
bar|20130925T0000Z|0|1|waiting
foo|20130923T0000Z|1|1|succeeded
foo|20130923T1200Z|1|1|succeeded
foo|20130924T0000Z|1|1|succeeded
foo|20130924T1200Z|1|1|succeeded
foo|20130925T0000Z|0|1|waiting
output_states|20130925T0000Z|0|1|waiting
__DB_DUMP__
contains_ok $TEST_DIR/post-restart-db <<'__DB_DUMP__'
bar|20130923T0000Z|1|1|succeeded
bar|20130923T1200Z|1|1|succeeded
bar|20130924T0000Z|1|1|succeeded
bar|20130924T1200Z|1|1|succeeded
bar|20130925T0000Z|0|1|waiting
foo|20130923T0000Z|1|1|succeeded
foo|20130923T1200Z|1|1|succeeded
foo|20130924T0000Z|1|1|succeeded
foo|20130924T1200Z|1|1|succeeded
foo|20130925T0000Z|0|1|waiting
shutdown|20130925T0000Z|1|1|succeeded
__DB_DUMP__
sqlite3 $(cylc get-global-config --print-run-dir)/$SUITE_NAME/cylc-suite.db \
 "select name, cycle, submit_num, try_num, status
  from task_states
  order by name, cycle;" > $TEST_DIR/db
cmp_ok $TEST_DIR/db <<'__DB_DUMP__'
bar|20130923T0000Z|1|1|succeeded
bar|20130923T1200Z|1|1|succeeded
bar|20130924T0000Z|1|1|succeeded
bar|20130924T1200Z|1|1|succeeded
bar|20130925T0000Z|1|1|succeeded
bar|20130925T1200Z|1|1|succeeded
bar|20130926T0000Z|1|1|succeeded
bar|20130926T1200Z|0|1|held
foo|20130923T0000Z|1|1|succeeded
foo|20130923T1200Z|1|1|succeeded
foo|20130924T0000Z|1|1|succeeded
foo|20130924T1200Z|1|1|succeeded
foo|20130925T0000Z|1|1|succeeded
foo|20130925T1200Z|1|1|succeeded
foo|20130926T0000Z|1|1|succeeded
foo|20130926T1200Z|0|1|held
output_states|20130925T0000Z|1|1|succeeded
shutdown|20130925T0000Z|1|1|succeeded
__DB_DUMP__
cmp_ok $TEST_DIR/state <<'__STATE__'
run mode : live
initial cycle : 20130923T0000Z
final cycle : 20130926T0000Z
(dp1
.
Begin task states
bar.20130925T1200Z : status=succeeded, spawned=true
bar.20130926T0000Z : status=succeeded, spawned=true
bar.20130926T1200Z : status=held, spawned=false
foo.20130926T0000Z : status=succeeded, spawned=true
foo.20130926T1200Z : status=held, spawned=false
__STATE__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
