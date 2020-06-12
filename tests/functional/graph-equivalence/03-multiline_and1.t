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
# Test graph = "a & b => c"
# gives the same result as
#      graph = """a => c
#                 b => c"""
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" 'multiline_and1'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-c"
cylc run "${SUITE_NAME}" --hold 1>'out' 2>&1
poll_grep_suite_log 'Holding all waiting or queued tasks now'
cylc show "${SUITE_NAME}" 'c.1' | sed -n "/prerequisites/,/outputs/p" > 'c-prereqs'
contains_ok "${TEST_SOURCE_DIR}/multiline_and_refs/c-ref" 'c-prereqs'
cylc shutdown "${SUITE_NAME}" --now -f
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
