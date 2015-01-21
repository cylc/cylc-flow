#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
# Test cat-view with a Jinja2 variable defined in a single cylc include-file
# TODO - another test for nested file inclusion
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok "$TEST_NAME" cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
# Run the convert-suggest-tool.
TEST_NAME=$TEST_NAME_BASE-5to6
run_ok "$TEST_NAME" cylc 5to6 "$TEST_DIR/$SUITE_NAME/suite.rc"
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
[scheduling]
    initial cycle point = 2014 # UPGRADE CHANGE: ISO 8601, 'time' -> 'point'
    cycling = Yearly  # UPGRADE INFO: change [[[m,n]]] dependency sections to [[[Yearly(m,n)]]] and re-run cylc 5to6.
    [[dependencies]]
        [[[2014,2]]]
            graph = "foo"
__OUT__
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
#purge_suite $SUITE_NAME
exit
