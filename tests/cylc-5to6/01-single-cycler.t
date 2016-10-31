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
# Test cat-view with a Jinja2 variable defined in a single cylc include-file
# TODO - another test for nested file inclusion
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 5
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_fail "$TEST_NAME" cylc validate $SUITE_NAME
cmp_ok "$TEST_NAME.stderr" <<'__ERR__'
Illegal item: [scheduling]initial cycle time
__ERR__
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
purge_suite $SUITE_NAME
exit
