#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test that reassigning a task to the same queue does not result in a warning.
# GitHub #3539
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
init_suite $TEST_NAME_BASE <<'__SUITE_RC__'
[scheduling]
   [[queues]]
       [[[q1]]]
           members = A, B
       [[[q2]]]
           members = x
   [[dependencies]]
       graph = "x => y"
[runtime]
   [[A]]
   [[B]]
   [[x]]
       inherit = A, B
   [[y]]
__SUITE_RC__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
# Validation should not warn about x being added to q1 from family B
# but it should warn about x being added to q2 (already added to q1).
cmp_ok ${TEST_NAME}.stderr - <<'__STDOUT__'
WARNING - Queue configuration warnings:
	+ q2: ignoring x (already assigned to a queue)
__STDOUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
