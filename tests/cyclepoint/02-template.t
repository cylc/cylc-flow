#!/bin/bash
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
# basic cylc cyclepoint --template option tests
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 12
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-extract
run_ok "${TEST_NAME}.strf" cylc cyclepoint --template foo-%Y-%m-%d-%H.nc 20140809T12
cmp_ok "${TEST_NAME}.strf.stdout" - << __OUT__
foo-2014-08-09-12.nc
__OUT__
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME}.yr" cylc cyclepoint --template CCYY 20140808T1200
cmp_ok "${TEST_NAME}.yr.stdout" - << __OUT__
2014
__OUT__
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME}.month" cylc cyclepoint --template CC 20140809T1200
cmp_ok "${TEST_NAME}.month.stdout" - << __OUT__
20
__OUT__
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME}.month" cylc cyclepoint --template MM 20140809T1200
cmp_ok "${TEST_NAME}.month.stdout" - << __OUT__
08
__OUT__
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME}.day" cylc cyclepoint --template DD 20140809T1200
cmp_ok "${TEST_NAME}.day.stdout" - << __OUT__
09
__OUT__
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME}.hour" cylc cyclepoint --template hh 20140809T1200
cmp_ok "${TEST_NAME}.hour.stdout" - << __OUT__
12
__OUT__
