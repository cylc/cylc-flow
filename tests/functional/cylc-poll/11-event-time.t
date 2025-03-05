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
# Test delayed poll gives the correct event time
. "$(dirname "$0")/test_header"

set_test_number 3
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"

RUND="$RUN_DIR/${WORKFLOW_NAME}"
sed -n 's/CYLC_JOB_EXIT_TIME=//p' "${RUND}/log/job/1/w1/NN/job.status" >'st-time.txt'
sqlite3 "${RUND}/log/db" "
    SELECT time_run_exit FROM task_jobs
    WHERE cycle=='1' AND name=='w1' AND submit_num=='1'" >'db-time.txt'
run_ok "${TEST_NAME_BASE}-time-run-exit" diff -u 'st-time.txt' 'db-time.txt'

purge
exit
