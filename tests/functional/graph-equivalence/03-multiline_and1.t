#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
install_workflow "${TEST_NAME_BASE}" 'multiline_and1'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
delete_db
TEST_NAME="${TEST_NAME_BASE}-check-c"
cylc play "${WORKFLOW_NAME}" --hold-after=1 1>'out' 2>&1
poll_grep_workflow_log 'Setting hold cycle point'
cylc show "${WORKFLOW_NAME}//1/c" | sed -n "/prerequisites/,/outputs/p" > 'c-prereqs'
contains_ok "${TEST_SOURCE_DIR}/multiline_and_refs/c-ref" 'c-prereqs'
cylc shutdown "${WORKFLOW_NAME}" --now
#-------------------------------------------------------------------------------
purge
