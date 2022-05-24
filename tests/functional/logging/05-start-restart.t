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
# Test scheduler logs create start/restart logs correctly


. "$(dirname "$0")/test_header"
set_test_number 7
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on stall timeout = true
        stall timeout = PT0S
        abort on inactivity timeout = true
        inactivity timeout = PT1M
[scheduling]
    [[graph]]
        R1 = foo => bar
[runtime]
    [[foo]]
        script = cylc__job__wait_cylc_message_started; cylc stop --now --now "${CYLC_WORKFLOW_ID}"
    [[bar]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug "${WORKFLOW_NAME}"

# wait for shut down
poll_grep_workflow_log "INFO - DONE"
find "${WORKFLOW_RUN_DIR}/log/scheduler" -type f -name "*-start*.log" | wc -l >'find-start-log'
cmp_ok 'find-start-log' <<< '1'
workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play --debug "${WORKFLOW_NAME}"
find "${WORKFLOW_RUN_DIR}/log/scheduler" -type f -name "*restart*.log" | wc -l >'find-restart-log'
cmp_ok 'find-restart-log' <<< '1'
grep_ok "Run: (re)start=1 log=1" "$HOME/cylc-run/${WORKFLOW_NAME}/log/scheduler/log"

# This tests that there is only one start and retart log created.
find "${WORKFLOW_RUN_DIR}/log/scheduler" -type f -name "*.log" | wc -l >'find-logs'
cmp_ok 'find-logs' <<< '2'

purge
