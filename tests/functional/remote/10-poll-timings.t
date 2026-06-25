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

# Test that the task_jobs DB table timings are consistent with the job.status
# file when comms method = poll.
export REQUIRE_PLATFORM='loc:remote comms:poll'
. "$(dirname "$0")/test_header"
set_test_number 6

create_test_global_config '' "
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        execution polling intervals = PT6S, PT1M
        submission polling intervals = PT6S, PT1M
        retrieve job logs = True
"

init_workflow "${TEST_NAME_BASE}" << __EOF__
[scheduler]
    [[events]]
        workflow timeout = PT40S
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        platform = ${CYLC_TEST_PLATFORM}
        script = sleep 2
__EOF__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "$TEST_NAME" cylc play "${WORKFLOW_NAME}" --no-detach -vv

# Should include both state changes from single poll
log_scan "${TEST_NAME_BASE}-log" "${WORKFLOW_RUN_DIR}/log/scheduler/log" \
    1 0 \
    "(polled)started" \
    "(polled)succeeded" \

sqlite3 "${WORKFLOW_RUN_DIR}/.service/db" \
    "SELECT time_submit_exit, time_run, time_run_exit FROM task_jobs;" \
    > db.out

JOB_STATUS_FILE="${WORKFLOW_RUN_DIR}/log/job/1/foo/01/job.status"
exists_ok "$JOB_STATUS_FILE"
# shellcheck disable=SC1090
. "$JOB_STATUS_FILE"

cmp_ok db.out <<< "${CYLC_JOB_RUNNER_SUBMIT_TIME}|${CYLC_JOB_INIT_TIME}|${CYLC_JOB_EXIT_TIME}"

purge
