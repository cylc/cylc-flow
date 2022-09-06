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
# ----------------------------------------------------------------------------

# Test reloading a stalled workflow: it should not stall again
# https://github.com/cylc/cylc-flow/issues/5103

. "$(dirname "$0")/test_header"
set_test_number 5

init_workflow "${TEST_NAME_BASE}" <<'__FLOW__'
[scheduler]
    [[events]]
        stall handlers = cylc reload %(workflow)s
        stall timeout = PT10S
        abort on stall timeout = True
        # Prevent infinite loop if the bug resurfaces
        workflow timeout = PT3M
        abort on workflow timeout = True
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = false
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach

LOG_FILE="${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Should only stall once
count_ok "CRITICAL - Workflow stalled" "$LOG_FILE" 1
# Stall event handler should only run once
count_ok "INFO - Reload completed" "$LOG_FILE" 1
# Stall timer should not stop at any point
grep_fail "stall timer stopped" "$LOG_FILE"

purge
