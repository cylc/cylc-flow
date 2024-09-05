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
# Workflow database content, broadcast + manual trigger to recover a failure.
. "$(dirname "$0")/test_header"
set_test_number 4
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"

DB_FILE="${RUN_DIR}/${WORKFLOW_NAME}/log/db"

if ! command -v sqlite3 > /dev/null; then
    skip 3 "sqlite3 not installed?"
    purge
    exit 0
fi

NAME='select-broadcast-events.out'
sqlite3 "${DB_FILE}" \
    'SELECT change, point, namespace, key, value FROM broadcast_events' >"${NAME}"
cmp_ok "${NAME}" <<'__SELECT__'
+|1|t1|[environment]HELLO|Hello
-|1|t1|[environment]HELLO|Hello
__SELECT__

NAME='select-task-jobs.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, submit_num, is_manual_submit, submit_status, run_status,
            platform_name, job_runner_name
     FROM task_jobs ORDER BY name' \
    >"${NAME}"
LOCALHOST="$(localhost_fqdn)"
# FIXME: recent Travis CI failure
sed -i "s/localhost/${LOCALHOST}/" "${NAME}"
cmp_ok "${NAME}" <<__SELECT__
1|recover-t1|1|0|0|0|${LOCALHOST}|background
1|t1|1|0|0|1|${LOCALHOST}|background
1|t1|2|1|0|0|${LOCALHOST}|background
__SELECT__

purge
exit
