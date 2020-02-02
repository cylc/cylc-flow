#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
set_test_number 21
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"

if ! command -v 'sqlite3' >'/dev/null'; then
    skip 7 "sqlite3 not installed?"
    purge_suite "${SUITE_NAME}"
    exit 0
fi

DB_FILE="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}/log/db"

NAME='schema.out'
ORIG="${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}"
SORTED_ORIG="sorted-${NAME}"
# The sqlite schema output depends on how the commands are executed. The .schema output will be
# exactly what was typed. This test should test whether the tables and columns exist. Not whether
# there is an extra newline or space before a column name. So we remove newlines, remove extra
# spaces, then add a newline after each semi-colon, which should give us a more stable test, using
# similar output, regardless of how the SQL command was formatted by the user.
sqlite3 "${DB_FILE}" ".schema" | tr -d '\n' | awk '$1=$1' | sed 's/;/;\n/g' | awk '$1=$1' | env LANG='C' sort >"${NAME}"
env LANG='C' sort "${ORIG}" > "${SORTED_ORIG}"
cmp_ok "${SORTED_ORIG}" "${NAME}"

NAME='select-suite-params.out'
sqlite3 "${DB_FILE}" \
    'SELECT key,value FROM suite_params WHERE key != "uuid_str" ORDER BY key' \
    >"${NAME}"
sed -i "s/$(cylc --version)/<SOME-VERSION>/g" "${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-events.out'
sqlite3 "${DB_FILE}" 'SELECT name, cycle, event, message FROM task_events' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-jobs.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, submit_num, try_num, submit_status, run_status,
            user_at_host, batch_sys_name
     FROM task_jobs ORDER BY name' \
    >"${NAME}"
LOCALHOST="$(hostname -f)"
# FIXME: recent Travis CI failure
sed -i "s/localhost/${LOCALHOST}/" "${NAME}"
cmp_ok "${NAME}" - <<__SELECT__
1|bar|1|1|0|0|${LOCALHOST}|background
1|baz|1|1|0|0|${LOCALHOST}|background
1|foo|1|1|0|0|${LOCALHOST}|background
__SELECT__

NAME='select-task-jobs-times.out'
sqlite3 "${DB_FILE}" \
    'SELECT time_submit,time_submit_exit,time_run,time_run_exit FROM task_jobs' \
    >"${NAME}"
# We want words not lines here
# shellcheck disable=2013
for DATE_TIME_STR in $(sed 's/[|]/ /g' "${NAME}"); do
    # Parse each string with "date --date=..." without the T
    run_ok "${NAME}-${DATE_TIME_STR}" \
        date --date="$(sed 's/T/ /' <<<"${DATE_TIME_STR}")"
done

NAME='select-task-pool.out'
sqlite3 "${DB_FILE}" 'SELECT name, cycle, spawned FROM task_pool ORDER BY name' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-task-states.out'
sqlite3 "${DB_FILE}" 'SELECT name, cycle, status FROM task_states ORDER BY name' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

NAME='select-inheritance.out'
sqlite3 "${DB_FILE}" 'SELECT namespace, inheritance FROM inheritance ORDER BY namespace' \
    >"${NAME}"
cmp_ok "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/${NAME}" "${NAME}"

purge_suite "${SUITE_NAME}"
exit
