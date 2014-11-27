#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
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
# Test cylc get-config with a suite with an explicitly empty final cycle point
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
init_suite "$TEST_NAME_BASE" "$TEST_SOURCE_DIR/$TEST_NAME_BASE/suite.rc"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-all
run_ok $TEST_NAME cylc get-config $SUITE_NAME --item='[scheduling]final cycle point'
cmp_ok $TEST_NAME.stdout - << __OUT__

__OUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
exit
