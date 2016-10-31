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
# Test execution retries are working
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE submission
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
sqlite3 \
    "$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/cylc-suite.db" \
    'select try_num, submit_num from task_jobs' >'select.out'
cmp_ok 'select.out' <<'__OUT__'
1|1
1|2
1|3
1|4
__OUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
