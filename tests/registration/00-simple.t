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
install_suite "${TEST_NAME_BASE}" 'basic'
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-register
run_ok $TEST_NAME cylc register "${SUITE_NAME}"
exists_ok "${SUITE_RUN_DIR}/.service/passphrase"
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
purge_suite "${SUITE_NAME}"
exit
