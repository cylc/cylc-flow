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
# Test "cylc set-verbosity"
. "$(dirname "$0")/test_header"
set_test_number 6

# Test illegal log level
TEST_NAME="${TEST_NAME_BASE}-bad"
run_fail "$TEST_NAME" cylc set-verbosity duck quack
grep_ok 'InputError: Illegal logging level, duck' "${TEST_NAME}.stderr"

# Test good log level
TEST_NAME="${TEST_NAME_BASE}-good"
init_workflow "${TEST_NAME_BASE}" << '__FLOW__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = andor
__FLOW__

run_ok "${TEST_NAME}-validate" cylc validate "$WORKFLOW_NAME"
workflow_run_ok "${TEST_NAME}-run" cylc play --pause "$WORKFLOW_NAME"

run_ok "$TEST_NAME" cylc set-verbosity DEBUG "$WORKFLOW_NAME"
log_scan "${TEST_NAME}-grep" "${WORKFLOW_RUN_DIR}/log/scheduler/log" 5 1 \
    'Command succeeded: set_verbosity'

cylc stop "$WORKFLOW_NAME"
purge
