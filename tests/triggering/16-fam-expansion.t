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
# Test correct expansion of (FOO:finish-all & FOO:fail-any)
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE fam-expansion
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --hold $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-show
run_ok $TEST_NAME cylc show $SUITE_NAME bar.1
#-------------------------------------------------------------------------------
contains_ok $TEST_NAME.stdout <<'__SHOW_DUMP__'
  -     LABEL: foo3_colon_succeed = foo3.1 succeeded
  -     LABEL: foo1_colon_succeed = foo1.1 succeeded
  -     LABEL: foo2_colon_succeed = foo2.1 succeeded
  -     LABEL: foo3_colon_fail = foo3.1 failed
  -     LABEL: foo2_colon_fail = foo2.1 failed
  -     LABEL: foo1_colon_fail = foo1.1 failed
__SHOW_DUMP__
#-------------------------------------------------------------------------------
cylc stop $SUITE_NAME
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
