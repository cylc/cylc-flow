#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test remote job logs retrieval OK with only "job.out" on a succeeded task.
CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
HOST=$(cylc get-global-config -i '[test battery]remote host' 2>'/dev/null')
if [[ -z "${HOST}" ]]; then
    skip_all '"[test battery]remote host": not defined'
fi
set_test_number 5
create_test_globalrc

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate -s "HOST=${HOST}" "${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach -s "HOST=${HOST}" "${SUITE_NAME}"

sed "/'job-logs-retrieve'/!d" \
    "${SUITE_RUN_DIR}/log/job/1/t1/01/job-activity.log" \
    >'edited-activities.log'
cmp_ok 'edited-activities.log' <<'__LOG__'
[(('job-logs-retrieve', 'failed'), 1) ret_code] 1
[(('job-logs-retrieve', 'failed'), 1) err] File(s) not retrieved: job.err
[(('job-logs-retrieve', 'failed'), 1) ret_code] 1
[(('job-logs-retrieve', 'failed'), 1) err] File(s) not retrieved: job.err
__LOG__
exists_ok "${SUITE_RUN_DIR}/log/job/1/t1/01/job.out"
exists_fail "${SUITE_RUN_DIR}/log/job/1/t1/01/job.err"

purge_suite_remote "${HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
