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
#C: Test one-off tasks
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE oneoff
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
run_ok $TEST_NAME cylc run --debug --reference-test $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-runs
TASKS=$(sqlite3 $(cylc get-global-config --print-run-dir)/$SUITE_NAME/cylc-suite.db "select count(*) from task_states where name is 'once'")
# manual comparison for the test
shift 1; if (($TASKS==1)); then ok $TEST_NAME; else fail $TEST_NAME; fi
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
