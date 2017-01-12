#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# basic cylc cyclepoint --template option tests
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 14
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-reformat
run_ok $TEST_NAME.print cylc cyclepoint --template foo-YYYY-MM-DD-HH.nc 2014080912
cmp_ok $TEST_NAME.print.stdout - << __OUT__
foo-2014-08-09-12.nc
__OUT__
#-------------------------------------------------------------------------------
run_ok $TEST_NAME.strf cylc cyclepoint --template foo-%Y-%m-%d-%H.nc 2014080912
cmp_ok $TEST_NAME.strf.stdout - << __OUT__
foo-2014-08-09-12.nc
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-extract
run_ok $TEST_NAME.yr cylc cyclepoint --template YYYY 2014080812
cmp_ok $TEST_NAME.yr.stdout - << __OUT__
2014
__OUT__
#-------------------------------------------------------------------------------
run_ok $TEST_NAME.month cylc cyclepoint --template CC 2014080912
cmp_ok $TEST_NAME.month.stdout - << __OUT__
20
__OUT__
#-------------------------------------------------------------------------------
run_ok $TEST_NAME.month cylc cyclepoint --template MM 2014080912
cmp_ok $TEST_NAME.month.stdout - << __OUT__
08
__OUT__
#-------------------------------------------------------------------------------
run_ok $TEST_NAME.day cylc cyclepoint --template DD 2014080912
cmp_ok $TEST_NAME.day.stdout - << __OUT__
09
__OUT__
#-------------------------------------------------------------------------------
run_ok $TEST_NAME.hour cylc cyclepoint --template HH 2014080912
cmp_ok $TEST_NAME.hour.stdout - << __OUT__
12
__OUT__
