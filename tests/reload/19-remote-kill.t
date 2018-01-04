#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Test reload then kill remote running task.
CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
TEST_HOST=$(cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')
if [[ -z "${TEST_HOST}" ]]; then
    skip_all '"[test battery]remote host": not defined'
fi

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate --set="CYLC_TEST_HOST=${TEST_HOST}" "${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test \
    --set="CYLC_TEST_HOST=${TEST_HOST}" \
     "${SUITE_NAME}"
if ! which sqlite3 > /dev/null; then
    skip 1 "sqlite3 not installed?"
    purge_suite "${SUITE_NAME}"
    exit 0
fi
sqlite3 "${SUITE_RUN_DIR}/.service/db" \
    'SELECT cycle,name,run_status FROM task_jobs' >'db.out'
cmp_ok 'db.out' <<'__OUT__'
1|foo|1
1|bar|0
__OUT__

purge_suite_remote "${TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
