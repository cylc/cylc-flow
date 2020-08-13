#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
# basic jinja2 expansion test
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 29
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-use-env-var
export CYLC_TASK_CYCLE_POINT=20100102T0300
run_ok "${TEST_NAME}.check-env" cylc cycle-point
run_ok "${TEST_NAME}.year-only" cylc cycle-point --print-year
cmp_ok "${TEST_NAME}.year-only.stdout" - << __OUT__
2010
__OUT__
run_ok "${TEST_NAME}.month-only" cylc cycle-point --print-month
cmp_ok "${TEST_NAME}.month-only.stdout" - << __OUT__
01
__OUT__
run_ok "${TEST_NAME}.day-only" cylc cycle-point --print-day
cmp_ok "${TEST_NAME}.day-only.stdout" - << __OUT__
02
__OUT__
run_ok "${TEST_NAME}.hour-only" cylc cycle-point --print-hour
cmp_ok "${TEST_NAME}.hour-only.stdout" - << __OUT__
03
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-offset-env-var
run_ok "${TEST_NAME}.year" cylc cycle-point --offset-years=10
cmp_ok "${TEST_NAME}.year.stdout" - << __OUT__
20200102T0300
__OUT__
run_ok "${TEST_NAME}.year-neg" cylc cycle-point --offset-years=-11
cmp_ok "${TEST_NAME}.year-neg.stdout" - << __OUT__
19990102T0300
__OUT__
run_ok "${TEST_NAME}.month" cylc cycle-point --offset-months=2
cmp_ok "${TEST_NAME}.month.stdout" - << __OUT__
20100302T0300
__OUT__
run_ok "${TEST_NAME}.month-neg" cylc cycle-point --offset-months=-1
cmp_ok "${TEST_NAME}.month-neg.stdout" - << __OUT__
20091202T0300
__OUT__
run_ok "${TEST_NAME}.day" cylc cycle-point --offset-days=10
cmp_ok "${TEST_NAME}.day.stdout" - << __OUT__
20100112T0300
__OUT__
run_ok "${TEST_NAME}.day-neg" cylc cycle-point --offset-days=-2
cmp_ok "${TEST_NAME}.day-neg.stdout" - << __OUT__
20091231T0300
__OUT__
run_ok "${TEST_NAME}.hour" cylc cycle-point --offset-hours=10
cmp_ok "${TEST_NAME}.hour.stdout" - << __OUT__
20100102T1300
__OUT__
run_ok "${TEST_NAME}.hour-neg" cylc cycle-point --offset-hours=-3
cmp_ok "${TEST_NAME}.hour-neg.stdout" - << __OUT__
20100102T0000
__OUT__
#-------------------------------------------------------------------------------
#Test with a supplied cycle time 
# N.B. this also checks environment variable being by CLI options
TEST_NAME="${TEST_NAME_BASE}-print-supplied-ctime"
run_ok "${TEST_NAME}.full" cylc cycle-point '2011-01-01'
cmp_ok "${TEST_NAME}.full.stdout" - <<<'2011-01-01'
run_ok "${TEST_NAME}-offset-week" cylc cycle-point --offset=P1W '20160301T06Z'
cmp_ok "${TEST_NAME}-offset-week.stdout" - <<<'20160308T06Z'
#-------------------------------------------------------------------------------
unset CYLC_TASK_CYCLE_TIME
