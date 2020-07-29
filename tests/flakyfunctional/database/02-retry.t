#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
# Suite database content, "task_jobs" table after a task retries.
. "$(dirname "$0")/test_header"
set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"

if ! command -v sqlite3 > /dev/null; then
    skip 1 "sqlite3 not installed?"
    purge_suite "${SUITE_NAME}"
    exit 0
fi

DB_FILE="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}/log/db"

NAME='select-task-jobs.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, submit_num, try_num, submit_status, run_status,
            user_at_host, batch_sys_name
     FROM task_jobs ORDER BY name' \
    >"${NAME}"
LOCALHOST="$(get_fqdn_by_host)"
# FIXME: recent Travis CI failure
sed -i "s/localhost/${LOCALHOST}/" "${NAME}"
cmp_ok "${NAME}" <<__SELECT__
20200101T0000Z|t1|1|1|0|1|${LOCALHOST}|background
20200101T0000Z|t1|2|2|0|1|${LOCALHOST}|background
20200101T0000Z|t1|3|3|0|0|${LOCALHOST}|background
__SELECT__

purge_suite "${SUITE_NAME}"
exit
