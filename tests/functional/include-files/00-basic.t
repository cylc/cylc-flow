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
# Test include-file inlining
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" suite
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
# test raw suite validates
run_ok "${TEST_NAME}.1" cylc val "${SUITE_NAME}"
# test suite validates as inlined during editing
cylc view --inline --mark-for-edit --stdout "${SUITE_NAME}" > inlined-for-edit.rc
run_ok "${TEST_NAME}.2" cylc val inlined-for-edit.rc
#-------------------------------------------------------------------------------
# compare inlined suite def with reference copy
TEST_NAME=${TEST_NAME_BASE}-compare
cylc view --inline --stdout "${SUITE_NAME}" > inlined.rc
cmp_ok inlined.rc "${TEST_SOURCE_DIR}/suite/ref-inlined.rc"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
#-------------------------------------------------------------------------------
