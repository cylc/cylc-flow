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
# Workflow database content, "task_jobs" table after a task retries.
. "$(dirname "$0")/test_header"
set_test_number 4
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"

# Ensure that DB statement and its args are printed to STDERR
grep -A 3 -F 'INFO - cannot execute database statement:' \
    "${TEST_NAME_BASE}-run.stderr" > "${TEST_NAME_BASE}-run.stderr.grep"
# The following "sed" turns the value for "time_submit_exit" to "?"
sed -i "s/, '[^T']*T[^Z']*Z',/, '?',/" "${TEST_NAME_BASE}-run.stderr.grep"
# Cannot use cmp_ok as the error message is prefixed by a timestamp.
grep_ok "INFO - cannot execute database statement:" \
    "${TEST_NAME_BASE}-run.stderr.grep"

DB_FILE="$RUN_DIR/${WORKFLOW_NAME}/log/db"

NAME='select-task-states.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, status FROM task_states ORDER BY name' \
    >"${NAME}"
cmp_ok "${NAME}" <<'__SELECT__'
1|done|succeeded
1|locker|succeeded
1|t0|succeeded
1|t1|succeeded
1|t2|succeeded
1|t3|succeeded
1|t4|succeeded
1|t5|succeeded
1|t6|succeeded
1|t7|succeeded
1|t8|succeeded
1|t9|succeeded
__SELECT__

purge
exit
