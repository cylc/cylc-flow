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
# Test "cylc verbosity"
. "$(dirname "$0")/test_header"
set_test_number 4

# Test illegal log level
TEST_NAME="${TEST_NAME_BASE}-bad"
run_fail "$TEST_NAME" cylc verbosity duck quack
grep_ok 'InputError: Illegal logging level, duck' "${TEST_NAME}.stderr"

# Test good log level
TEST_NAME="${TEST_NAME_BASE}-good"
init_workflow "${TEST_NAME_BASE}" << '__FLOW__'
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
[scheduling]
    [[graph]]
        R1 = setter => getter
[runtime]
    [[setter]]
        script = """
            echo "CYLC_VERBOSE: $CYLC_VERBOSE"
            [[ "$CYLC_VERBOSE" != 'true' ]]
            echo "CYLC_DEBUG: $CYLC_DEBUG"
            [[ "$CYLC_DEBUG" != 'true' ]]

            cylc verbosity DEBUG "$CYLC_WORKFLOW_ID"
            cylc__job__poll_grep_workflow_log 'Command "set_verbosity" actioned'
        """
    [[getter]]
        script = """
            echo "CYLC_VERBOSE: $CYLC_VERBOSE"
            [[ "$CYLC_VERBOSE" == 'true' ]]
            echo "CYLC_DEBUG: $CYLC_DEBUG"
            [[ "$CYLC_DEBUG" == 'true' ]]
        """
__FLOW__

run_ok "${TEST_NAME}-validate" cylc validate "$WORKFLOW_NAME"
workflow_run_ok "${TEST_NAME}-run" cylc play --no-detach "$WORKFLOW_NAME"
purge
