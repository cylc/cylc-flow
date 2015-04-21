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
# Test all current non-silent suite obsoletions and deprecations.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_ok $TEST_NAME cylc validate -v $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-cmp
cylc validate -v $SUITE_NAME 2>&1 | egrep '^ \* ' > val.out
cmp_ok val.out <<__END__
 * (5.2.0) [cylc][event handler execution] -> [cylc][event handler submission] - value unchanged
 * (5.4.7) [scheduling][special tasks][explicit restart outputs] - DELETED (OBSOLETE)
 * (5.4.11) [cylc][accelerated clock] - DELETED (OBSOLETE)
 * (6.0.0) [visualization][runtime graph] - DELETED (OBSOLETE)
 * (6.0.0) [development] - DELETED (OBSOLETE)
 * (6.0.0) [scheduling][initial cycle time] -> [scheduling][initial cycle point] - changed naming to reflect non-date-time cycling
 * (6.0.0) [scheduling][final cycle time] -> [scheduling][final cycle point] - changed naming to reflect non-date-time cycling
 * (6.0.0) [visualization][initial cycle time] -> [visualization][initial cycle point] - changed naming to reflect non-date-time cycling
 * (6.0.0) [visualization][final cycle time] -> [visualization][final cycle point] - changed naming to reflect non-date-time cycling
 * (6.0.0) [cylc][job submission] - DELETED (OBSOLETE)
 * (6.0.0) [cylc][event handler submission] - DELETED (OBSOLETE)
 * (6.0.0) [cylc][poll and kill command submission] - DELETED (OBSOLETE)
 * (6.0.0) [cylc][lockserver] - DELETED (OBSOLETE)
 * (6.1.3) [visualization][enable live graph movie] - DELETED (OBSOLETE)
__END__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
