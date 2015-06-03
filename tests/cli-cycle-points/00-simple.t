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
# Test that initial and final cycle points can be overridden by the CLI.
# Ref. Github Issue #1406.

. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run-override
# This will fail if the in-suite final cycle point does not get overridden.
suite_run_ok $TEST_NAME cylc run --until=2015-04 --debug $SUITE_NAME 2015-04
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run-fail
# This should fail as the final cycle point  is < the initial one.
suite_run_fail $TEST_NAME cylc run --until=2015-03 --debug $SUITE_NAME 2015-04
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
