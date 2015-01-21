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
# Test validation with a prev-style cycle point and a new-style ^ offset.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE
run_fail $TEST_NAME cylc validate --debug -v -v $SUITE_NAME
grep_ok "Conflicting syntax: pre-cylc-6 syntax \
(initial/final cycle point format: CCYYMMDDhh) \
vs post-cylc-6 syntax \
(graphnode: cold_foo\[^T00\]: ISO 8601 offset)" $TEST_NAME.stderr
#-------------------------------------------------------------------------------
exit
