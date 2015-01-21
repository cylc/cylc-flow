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
# Test cylc get-config
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 14
#-------------------------------------------------------------------------------
init_suite "$TEST_NAME_BASE" "$TEST_SOURCE_DIR/$TEST_NAME_BASE/suite.rc"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-all
run_ok $TEST_NAME cylc get-config $SUITE_NAME
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section1
run_ok $TEST_NAME cylc get-config --item=[scheduling] $SUITE_NAME
cmp_ok $TEST_NAME.stdout "$TEST_SOURCE_DIR/$TEST_NAME_BASE/section1.stdout"
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section1-section
run_ok $TEST_NAME cylc get-config --item=[scheduling][dependencies] $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
graph = OPS:finish-all => VAR
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section1-section-option
run_ok $TEST_NAME \
    cylc get-config --item=[scheduling][dependencies][graph] $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
OPS:finish-all => VAR
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section2
run_ok $TEST_NAME cylc get-config --item=[runtime] $SUITE_NAME
cmp_ok $TEST_NAME.stdout "$TEST_SOURCE_DIR/$TEST_NAME_BASE/section2.stdout"
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
