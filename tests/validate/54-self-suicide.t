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
# Test strict validation of suite for tasks with inherit = [blank]
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-val
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-graph-check
run_ok $TEST_NAME cylc graph --reference $SUITE_NAME
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
edge "bar.1" "baz.1" solid
edge "foo.1" "bar.1" solid
edge "foo.1" "qux.1" solid
edge "qux.1" "baz.1" solid
graph
node "bar.1" "bar\n1" unfilled box black
node "baz.1" "baz\n1" unfilled box black
node "foo.1" "foo\n1" unfilled box black
node "qux.1" "qux\n1" unfilled box black
stop
__OUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
