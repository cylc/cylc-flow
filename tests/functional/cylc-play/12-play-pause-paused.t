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
#
# Test that running ``cylc play --pause`` on a paused workflow will _not_
# upause it, but will return a warning.
# https://github.com/cylc/cylc-flow/issues/7006

. "$(dirname "$0")/test_header"
set_test_number 3

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = a
__FLOW_CONFIG__

# It starts the workflow paused:
run_ok "${TEST_NAME_BASE}-start-paused" \
    cylc play "${WORKFLOW_NAME}" --pause

# It fails to unpause the workflow:
run_ok "${TEST_NAME_BASE}-start-paused-again" \
    cylc play "${WORKFLOW_NAME}" --pause

# It returns an informative error:
grep_ok "Workflow already running: Remove --pause to resume" \
    "${TEST_NAME_BASE}-start-paused-again.stderr"

cylc stop "${WORKFLOW_NAME}" --now --now

poll_workflow_stopped

purge
