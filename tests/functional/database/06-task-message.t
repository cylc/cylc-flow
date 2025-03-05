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
# Workflow database content, "task_events" table contains unhandled task messages
. "$(dirname "$0")/test_header"
set_test_number 3
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"

DB_FILE="$RUN_DIR/${WORKFLOW_NAME}/log/db"

NAME='select-task-events.out'
sqlite3 "${DB_FILE}" "
    SELECT
        cycle, name, event, message
    FROM
        task_events
    WHERE
        event GLOB 'message *'
    ORDER BY
        event
" >"${NAME}"
cmp_ok "${NAME}" <<'__SELECT__'
1|t1|message critical|You are being critical
1|t1|message info|You are normal
1|t1|message warning|You have been warned
__SELECT__

purge
exit
