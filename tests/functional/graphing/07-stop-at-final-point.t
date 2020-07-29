#!/usr/bin/env bash
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
# Test that graphing stops at suite final cycle point.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-graph-npoints"
graph_suite "${SUITE_NAME}" 'graph.plain.test1' --set="STOP_CRITERION=number of cycle points = 6"
cmp_ok 'graph.plain.test1' "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/graph.plain.ref"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-graph-final-point"
graph_suite "${SUITE_NAME}" 'graph.plain.test2' --set="STOP_CRITERION=final cycle point = 2015-01-05"
cmp_ok 'graph.plain.test2' "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/graph.plain.ref"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
