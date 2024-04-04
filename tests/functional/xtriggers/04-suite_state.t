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

# Test that deprecation warnings are printed appropriately for the suite_state
# xtrigger.

. "$(dirname "$0")/test_header"

set_test_number 4

init_workflow "$TEST_NAME_BASE" << __FLOW_CONFIG__
[scheduling]
    initial cycle point = 2000
    [[dependencies]]
        [[[R1]]]
            graph = @upstream => foo
    [[xtriggers]]
        upstream = suite_state(suite=thorin/oin/gloin, task=mithril, point=1)
[runtime]
    [[foo]]
__FLOW_CONFIG__

msg='WARNING - The suite_state xtrigger is deprecated'

TEST_NAME="${TEST_NAME_BASE}-val"
run_ok "$TEST_NAME" cylc validate "$WORKFLOW_NAME"

grep_ok "$msg" "${TEST_NAME}.stderr"

# Rename flow.cylc to suite.rc:
mv "${WORKFLOW_RUN_DIR}/flow.cylc" "${WORKFLOW_RUN_DIR}/suite.rc"

TEST_NAME="${TEST_NAME_BASE}-val-2"
run_ok "$TEST_NAME" cylc validate "$WORKFLOW_NAME"

grep_fail "$msg" "${TEST_NAME}.stderr"
