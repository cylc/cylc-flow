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
# Test restart with held tasks
. "$(dirname "$0")/test_header"
set_test_number 5
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" --debug --no-detach --abort-if-any-task-fails

T1_2016_PID="$(sed -n 's/CYLC_JOB_PID=//p' "${WORKFLOW_RUN_DIR}/log/job/2016/t1/01/job.status")"
poll_pid_done "${T1_2016_PID}"

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT cycle, name, status FROM task_pool WHERE is_held IS 1 ORDER by cycle, name' >'workflow-stopped.out'
cmp_ok 'workflow-stopped.out' <<'__OUT__'
2016|t2|waiting
2017|t1|waiting
__OUT__

# Restart
cylc play "${WORKFLOW_NAME}" --debug --no-detach 1>"${TEST_NAME_BASE}-restart.out" 2>&1 &
CYLC_RESTART_PID=$!
poll_workflow_running

cylc release "${WORKFLOW_NAME}//2016/t2"
poll_grep 'CYLC_JOB_EXIT' "${WORKFLOW_RUN_DIR}/log/job/2016/t2/01/job.status"

cylc release --all "${WORKFLOW_NAME}"
cylc poll "${WORKFLOW_NAME}//*"

# Ensure workflow has completed
run_ok "${TEST_NAME_BASE}-restart" wait "${CYLC_RESTART_PID}"

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name' >'task-pool.out'
cmp_ok 'task-pool.out' < /dev/null

purge
exit
