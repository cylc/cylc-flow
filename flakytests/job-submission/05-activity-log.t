#!/bin/bash
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
# Test writing various messages to the job activity log.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"

T1_ACTIVITY_LOG="${SUITE_RUN_DIR}/log/job/1/t1/NN/job-activity.log"
grep_ok '\[jobs-submit ret_code\] 0' "${T1_ACTIVITY_LOG}"
grep_ok '\[jobs-kill ret_code\] 1' "${T1_ACTIVITY_LOG}"
grep_ok '\[jobs-kill out\] [^|]*|1/t1/01|1' "${T1_ACTIVITY_LOG}"
grep_ok '\[jobs-poll out\] [^|]*|1/t1/01|{"batch_sys_name": "background", "batch_sys_job_id": "[^\"]*", "batch_sys_exit_polled": 1, "time_submit_exit": "[^\"]*", "time_run": "[^\"]*"}' "${T1_ACTIVITY_LOG}"
grep_ok "\\[(('event-handler-00', 'failed'), 1) out\\] failed ${SUITE_NAME} \
t1\\.1 job failed" "${T1_ACTIVITY_LOG}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
