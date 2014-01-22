#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
#C: Basic test for state dumps, specify the dump on restart command line.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 8
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
SUITE_DIR=$(cylc get-global-config --print-run-dir)/$SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
ln -s reference.log.run $TEST_DIR/$SUITE_NAME/reference.log
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
# Number of dumps
run_ok $TEST_NAME-n-dumps test $(find $SUITE_DIR/state -type f | wc -l) -eq 10
# Contents in dump before restart
grep -e '^initial cycle' -e '^final cycle' -e 't1\.' \
    $SUITE_DIR/state/state >$TEST_NAME.state
cmp_ok $TEST_NAME.state <<'__STATE__'
initial cycle : 2013010100
final cycle : 2013011000
t1.2013010600 : status=ready, spawned=false
__STATE__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-restart
rm $TEST_DIR/$SUITE_NAME/reference.log
ln -s reference.log.restart $TEST_DIR/$SUITE_NAME/reference.log
STATE_BEFORE_RESTART=$(readlink $SUITE_DIR/state/state)
rm $SUITE_DIR/state/state
suite_run_ok $TEST_NAME cylc restart --reference-test --debug $SUITE_NAME \
    $STATE_BEFORE_RESTART
# Check restart dump is the same as last dump before restart
STATE_USED_TO_RESTART=$(readlink $(echo $SUITE_DIR/state/state-restart*))
run_ok $TEST_NAME.state-restart \
    test $STATE_BEFORE_RESTART = $STATE_USED_TO_RESTART
# Number of dumps
run_ok $TEST_NAME-n-dumps test $(find $SUITE_DIR/state -type f | wc -l) -eq 20
# Contents in dump at final cycle
grep -e '^initial cycle' -e '^final cycle' -e 't1\.' \
    $SUITE_DIR/state/state >$TEST_NAME.state
cmp_ok $TEST_NAME.state <<'__STATE__'
initial cycle : 2013010100
final cycle : 2013011000
t1.2013011000 : status=succeeded, spawned=true
t1.2013011100 : status=held, spawned=false
__STATE__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
