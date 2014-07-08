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
# Test graph = """a => b
#                 b => c""" gives the same result as
#      graph = "a => b => c"
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE test2
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-a
cylc run $SUITE_NAME --hold
cylc show $SUITE_NAME a.1 | sed -n "/PREREQUISITES/,/OUTPUTS/p" > a-prereqs
cmp_ok $TEST_SOURCE_DIR/splitline_refs/a-ref a-prereqs
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-b
cylc show $SUITE_NAME b.1 | sed -n "/PREREQUISITES/,/OUTPUTS/p" > b-prereqs
cmp_ok $TEST_SOURCE_DIR/splitline_refs/b-ref b-prereqs
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-check-c
cylc show $SUITE_NAME c.1 | sed -n "/PREREQUISITES/,/OUTPUTS/p" > c-prereqs
cmp_ok $TEST_SOURCE_DIR/splitline_refs/c-ref c-prereqs
#-------------------------------------------------------------------------------
cylc shutdown $SUITE_NAME --now -f
purge_suite $SUITE_NAME
