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
# Test restart with stop task

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
        'SELECT value FROM workflow_params WHERE key=="stop_task";' >'stoptask.out'
    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' >'taskpool.out'
}

set_test_number 10

# Event should look like this:
# Start workflow
# At 1/t1, set stop task to 1/t5
# At 1/t2, stop workflow at 1/t2
# Restart
# Workflow runs to stop task 1/t5, reset stop task.
# Restart
# Workflow stops normally at 1/t8
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[task parameters]
    i = 1..8
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
        abort on inactivity timeout = True
        inactivity timeout = P1M
[scheduling]
    [[graph]]
        R1 = t<i-1> => t<i>
[runtime]
    [[t<i>]]
        script = true
    [[t<i=1>]]
        script = cylc stop "${CYLC_WORKFLOW_ID}//1/t_i5"
    [[t<i=2>]]
        script = cylc stop "${CYLC_WORKFLOW_ID}"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --no-detach
dumpdbtables
cmp_ok 'stoptask.out' <<<'1/t_i5'
cmp_ok 'taskpool.out' <<'__OUT__'
1|t_i3|waiting
__OUT__

workflow_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc play "${WORKFLOW_NAME}" --no-detach
dumpdbtables
cmp_ok 'stoptask.out' <<<''
cmp_ok 'taskpool.out' <<'__OUT__'
1|t_i6|waiting
__OUT__

workflow_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc play "${WORKFLOW_NAME}" --no-detach
dumpdbtables
cmp_ok 'stoptask.out' <<<''
cmp_ok 'taskpool.out' <'/dev/null'

purge
exit
