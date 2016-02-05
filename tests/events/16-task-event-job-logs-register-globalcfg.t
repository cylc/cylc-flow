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
# Test remote job logs retrieval, requires compatible version of cylc on remote
# job host.
. "$(dirname "$0")/test_header"
set_test_number 5

create_test_globalrc '' $'
[task events]
    register job logs retry delays = PT0S, PT15S'

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}"

SUITE_RUN_DIR="$(cylc get-global-config '--print-run-dir')/${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/cylc-suite.db" \
    'select cycle,name,submit_num,filename,location from task_job_logs
     ORDER BY cycle,name,submit_num,filename' >'select-task-job-logs.out'
cmp_ok 'select-task-job-logs.out' <<'__OUT__'
1|t1|1|job|1/t1/01/job
1|t1|1|job-activity.log|1/t1/01/job-activity.log
1|t1|1|job.err|1/t1/01/job.err
1|t1|1|job.out|1/t1/01/job.out
1|t1|1|job.out.keep|1/t1/01/job.out.keep
1|t1|1|job.status|1/t1/01/job.status
__OUT__

sed "/'job-logs-register'/!d; s/^[^ ]* //" \
    "${SUITE_RUN_DIR}/log/job/1/t1/01/job-activity.log" \
    >'edited-activities.log'
cmp_ok 'edited-activities.log' <<'__LOG__'
[('job-logs-register', 1) ret_code] 0
__LOG__

grep -F 'failed, retrying in' "${SUITE_RUN_DIR}/log/suite/log" \
    | cut -d' ' -f 4-10 | sort >"edited-log"
    cmp_ok 'edited-log' <<'__LOG__'
[t1.1] -('job-logs-register', 1) failed, retrying in PT15S
__LOG__

purge_suite "${SUITE_NAME}"
exit
