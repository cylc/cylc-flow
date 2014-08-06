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
# basic jinja2 expansion test
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 27
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-use-env-var
export CYLC_TASK_CYCLE_POINT=2010010203
run_ok $TEST_NAME.check-env cylc cycletime
run_ok $TEST_NAME.year-only cylc cycletime --print-year
cmp_ok $TEST_NAME.year-only.stdout - << __OUT__
2010
__OUT__
run_ok $TEST_NAME.month-only cylc cycletime --print-month
cmp_ok $TEST_NAME.month-only.stdout - << __OUT__
01
__OUT__
run_ok $TEST_NAME.day-only cylc cycletime --print-day
cmp_ok $TEST_NAME.day-only.stdout - << __OUT__
02
__OUT__
run_ok $TEST_NAME.hour-only cylc cycletime --print-hour
cmp_ok $TEST_NAME.hour-only.stdout - << __OUT__
03
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-offset-env-var
run_ok $TEST_NAME.year cylc cycletime --offset-years=10
cmp_ok $TEST_NAME.year.stdout - << __OUT__
2020010203
__OUT__
run_ok $TEST_NAME.year-neg cylc cycletime --offset-years=-11
cmp_ok $TEST_NAME.year-neg.stdout - << __OUT__
1999010203
__OUT__
run_ok $TEST_NAME.month cylc cycletime --offset-months=2
cmp_ok $TEST_NAME.month.stdout - << __OUT__
2010030203
__OUT__
run_ok $TEST_NAME.month-neg cylc cycletime --offset-months=-1
cmp_ok $TEST_NAME.month-neg.stdout - << __OUT__
2009120203
__OUT__
run_ok $TEST_NAME.day cylc cycletime --offset-days=10
cmp_ok $TEST_NAME.day.stdout - << __OUT__
2010011203
__OUT__
run_ok $TEST_NAME.day-neg cylc cycletime --offset-days=-2
cmp_ok $TEST_NAME.day-neg.stdout - << __OUT__
2009123103
__OUT__
run_ok $TEST_NAME.hour cylc cycletime --offset-hours=10
cmp_ok $TEST_NAME.hour.stdout - << __OUT__
2010010213
__OUT__
run_ok $TEST_NAME.hour-neg cylc cycletime --offset-hours=-3
cmp_ok $TEST_NAME.hour-neg.stdout - << __OUT__
2010010200
__OUT__
#-------------------------------------------------------------------------------
#Test with a supplied cycle time 
# N.B. this also checks environment variable being by CLI options
TEST_NAME=$TEST_NAME_BASE-print-supplied-ctime
run_ok $TEST_NAME.full cylc cycletime 20110101T01
cmp_ok $TEST_NAME.full.stdout - << __OUT__
20110101T01
__OUT__
#-------------------------------------------------------------------------------
unset CYLC_TASK_CYCLE_TIME

#TODO add tests either in here for ISO8601 or in separate ISO8601 test with same operations
