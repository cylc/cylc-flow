#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Suite database content, a basic non-cycling suite of 3 tasks
. "$(dirname "$0")/test_header"
set_test_number 7
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug "${SUITE_NAME}"

DB_FILE="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}/cylc-suite.db"

NAME='schema.out'
sqlite3 "${DB_FILE}" ".schema" | sort >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-states.out'
sqlite3 "${DB_FILE}" 'SELECT name, cycle, status FROM task_states ORDER BY name' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-events.out'
sqlite3 "${DB_FILE}" 'SELECT name, cycle, event, message, misc FROM task_events' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-job-logs.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, submit_num, key, path
     FROM task_job_logs ORDER BY name, key' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-jobs.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, submit_num, try_num, submit_status, run_status,
            user_at_host, batch_sys_name
     FROM task_jobs ORDER BY name' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

purge_suite "${SUITE_NAME}"
exit
