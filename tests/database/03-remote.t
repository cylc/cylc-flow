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
# Suite database content, "task_jobs" table with a remote job.
. "$(dirname "$0")/test_header"
export CYLC_TEST_HOST=$(cylc get-global-config -i '[test battery]remote host')
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '[test battery]remote host: not defined'
fi
set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# Install suite passphrase.
set -eu
SSH='ssh -oBatchMode=yes -oConnectTimeout=5'
${SSH} "${CYLC_TEST_HOST}" \
    "mkdir -p .cylc/${SUITE_NAME}/ && cat >.cylc/${SUITE_NAME}/passphrase" \
    <"${TEST_DIR}/${SUITE_NAME}/passphrase"
set +eu

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --reference-test "${SUITE_NAME}"

DB_FILE="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}/cylc-suite.db"

NAME='select-task-jobs.out'
sqlite3 "${DB_FILE}" \
    'SELECT cycle, name, submit_num, try_num, submit_status, run_status,
            user_at_host, batch_sys_name
     FROM task_jobs ORDER BY name' \
    >"${NAME}"
cmp_ok "${NAME}" <<__SELECT__
20200101T0000Z|t1|1|1|0|0|localhost|background
20200101T0000Z|t2|1|1|0|0|${CYLC_TEST_HOST}|background
__SELECT__

if [[ "$CYLC_TEST_HOST" != 'localhost' ]]; then
    $SSH -n "$CYLC_TEST_HOST" "rm -rf '.cylc/$SUITE_NAME' 'cylc-run/$SUITE_NAME'"
fi
purge_suite "${SUITE_NAME}"
exit
