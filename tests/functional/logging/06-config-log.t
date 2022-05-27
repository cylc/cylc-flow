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
# Test start/restart/reload config logs are created correctly

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
    cycling mode = integer
    initial cycle point = 1
    final cycle point = 2
    [[graph]]
        P1 = """foo => bar
                bar[-P1] =>foo
        """
[runtime]
    [[foo]]
        script = cylc__job__wait_cylc_message_started;sleep 20; cylc reload "${CYLC_WORKFLOW_ID}"
    [[bar]]
        script = cylc stop --now --now "${CYLC_WORKFLOW_ID}"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug "${WORKFLOW_NAME}"

# wait for shut down
poll_grep_workflow_log "INFO - DONE"

# Check config logs.

exists_ok "${WORKFLOW_RUN_DIR}/log/config/01-start-01.cylc"
exists_ok "${WORKFLOW_RUN_DIR}/log/config/02-reload-01.cylc"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug "${WORKFLOW_NAME}"
poll_grep_workflow_log "INFO - DONE"

exists_ok "${WORKFLOW_RUN_DIR}/log/config/03-restart-02.cylc"
exists_ok "${WORKFLOW_RUN_DIR}/log/config/04-reload-02.cylc"

purge