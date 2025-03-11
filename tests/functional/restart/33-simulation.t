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
# Test https://github.com/cylc/cylc-flow/issues/2788
. "$(dirname "$0")/test_header"

set_test_number 5
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    cycle point format = %Y
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
[scheduling]
    initial cycle point = 2018
    [[graph]]
        P1Y = t1
[runtime]
    [[t1]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --no-detach --stopcp=2019 --mode=simulation --abort-if-any-task-fails "${WORKFLOW_NAME}"
# Force a waiting task into a running task
run_ok "${TEST_NAME_BASE}-sql1" sqlite3 "${HOME}/cylc-run/${WORKFLOW_NAME}/.service/db" \
    "UPDATE task_states SET status='running' WHERE name=='t1' AND cycle=='2019'"
run_ok "${TEST_NAME_BASE}-sql1" sqlite3 "${HOME}/cylc-run/${WORKFLOW_NAME}/.service/db" \
    "UPDATE task_pool SET status='running' WHERE name=='t1' AND cycle=='2019'"
workflow_run_ok "${TEST_NAME_BASE}-restart" \
    cylc play --debug --no-detach --fcp=2020 --mode=simulation --abort-if-any-task-fails "${WORKFLOW_NAME}"
purge
exit
