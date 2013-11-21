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
# Validate and run the suite-state/polling test suite
# The test suite is in polling/; it depends on another suite in upstream/

. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE polling
#-------------------------------------------------------------------------------
# copy the upstream suite to the test directory and register it
cp -r $TEST_SOURCE_DIR/upstream $TEST_DIR/
# use full range of characters in the suite-to-be-polled name:
UPSTREAM=${SUITE_NAME}-up_stre.am
cylc unreg $UPSTREAM
cylc reg $UPSTREAM $TEST_DIR/upstream
#-------------------------------------------------------------------------------
# validate both suites as tests
TEST_NAME=$TEST_NAME_BASE-validate-upstream
run_ok $TEST_NAME cylc val $UPSTREAM

TEST_NAME=$TEST_NAME_BASE-validate-polling
run_ok $TEST_NAME cylc val --set UPSTREAM=$UPSTREAM $SUITE_NAME

#-------------------------------------------------------------------------------
# run the upstream suite and detach (not a test)
cylc run $UPSTREAM

#-------------------------------------------------------------------------------
# run the suite-state polling test suite
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug --set UPSTREAM=$UPSTREAM $SUITE_NAME

#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME

#-------------------------------------------------------------------------------
# clean up the upstream suite
# just in case (expect error message here, but exit 0):
cylc stop --now $UPSTREAM --max-polls=20 --interval=2 > /dev/null 2>&1
rm -rf $( cylc get-global-config --print-run-dir )/$UPSTREAM
cylc unreg $UPSTREAM

