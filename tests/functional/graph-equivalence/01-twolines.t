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
# Test graph = """a => b
#                 b => c""" gives the same result as
#      graph = "a => b => c"
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" test2
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate \
    --set=TEST_OUTPUT_PATH="${PWD}" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --reference-test --debug --no-detach \
    --set=TEST_OUTPUT_PATH="${PWD}" "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-a"
cmp_ok "${TEST_SOURCE_DIR}/splitline_refs/a-ref" 'a-prereqs'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-b"
poll_grep_suite_log 'INFO - DONE'
cmp_ok "${TEST_SOURCE_DIR}/splitline_refs/b-ref" 'b-prereqs'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-c"
cmp_ok "${TEST_SOURCE_DIR}/splitline_refs/c-ref" 'c-prereqs'
#-------------------------------------------------------------------------------
cylc shutdown "${SUITE_NAME}" --now
purge
