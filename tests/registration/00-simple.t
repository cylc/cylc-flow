#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test cylc suite registration
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
SUITE_NAME=$(date -u +%Y%m%dT%H%M%SZ)_cylc_test_$(basename $TEST_SOURCE_DIR)_regtest
mkdir $TEST_DIR/$SUITE_NAME/ 2>&1 
cp -r $TEST_SOURCE_DIR/basic/* $TEST_DIR/$SUITE_NAME 2>&1
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-register
run_ok $TEST_NAME cylc register $SUITE_NAME $TEST_DIR/$SUITE_NAME
RUND="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
exists_ok "${RUND}/.cylc-var/passphrase"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-get-dir
run_ok $TEST_NAME cylc get-directory $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
cd .. # necessary so the suite is being validated via the database not filepath
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-print-db
cylc print 1>'dboutput' 2>'/dev/null'
grep_ok "$SUITE_NAME" 'dboutput'
#-------------------------------------------------------------------------------
if [[ -n ${TEST_DIR:-} ]]; then
    rm -rf $TEST_DIR/$SUITE_NAME/
fi
#-------------------------------------------------------------------------------
