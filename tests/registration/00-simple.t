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
#C: Test cylc suite registration
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 8
#-------------------------------------------------------------------------------
SUITE_NAME=$(date -u +%Y%m%d%H%M)_cylc_test_$(basename $TEST_SOURCE_DIR)_regtest
mkdir $TEST_DIR/$SUITE_NAME/ 2>&1 
cp -r $TEST_SOURCE_DIR/basic/* $TEST_DIR/$SUITE_NAME 2>&1
cylc unregister $SUITE_NAME 2>&1
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-register
run_ok $TEST_NAME cylc register $SUITE_NAME $TEST_DIR/$SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-dir
run_ok $TEST_NAME cylc get-directory $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
cd .. # necessary so the suite is being validated via the database not filepath
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-print-db
cylc print 1> dboutput
run_ok $TEST_NAME grep $SUITE_NAME dboutput
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-unreg
run_ok $TEST_NAME cylc unregister $SUITE_NAME
run_fail $TEST_NAME-check cylc get-directory $SUITE_NAME
cylc print 1> dboutput-unregd
run_fail $TEST_NAME-unreg-dbcheck grep $SUITE_NAME dboutput-unregd
run_fail $TEST_NAME-val-fail cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
if [[ -n ${TEST_DIR:-} ]]; then
    rm -rf $TEST_DIR/$SUITE_NAME/
fi
#-------------------------------------------------------------------------------
