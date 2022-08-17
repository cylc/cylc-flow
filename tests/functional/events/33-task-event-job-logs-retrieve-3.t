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
# Test remote job logs retrieval OK with only "job.out" on a succeeded task.
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 5

create_test_global_config "" "
[platforms]
    [[blackbriar]]
        hosts = ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        retrieve job logs retry delays = 2*PT5S
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --reference-test -vv --no-detach "${WORKFLOW_NAME}"

sed "/'job-logs-retrieve'/!d" \
    "${WORKFLOW_RUN_DIR}/log/job/1/t1/01/job-activity.log" \
    >'edited-activities.log'
cmp_ok 'edited-activities.log' <<'__LOG__'
[(('job-logs-retrieve', 'failed'), 1) ret_code] 1
[(('job-logs-retrieve', 'failed'), 1) err] File(s) not retrieved: job.err
[(('job-logs-retrieve', 'failed'), 1) ret_code] 1
[(('job-logs-retrieve', 'failed'), 1) err] File(s) not retrieved: job.err
__LOG__
exists_ok "${WORKFLOW_RUN_DIR}/log/job/1/t1/01/job.out"
exists_fail "${WORKFLOW_RUN_DIR}/log/job/1/t1/01/job.err"

purge
exit
