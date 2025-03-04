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

# Test that removing submited/running tasks causes them to be killed.
# Any downstream tasks that depend on the `:submit-fail`/`:fail` outputs
# should NOT run.
# Handlers for the `submission failed`/`failed` events should not run either.

export REQUIRE_PLATFORM='runner:at'
. "$(dirname "$0")/test_header"
set_test_number 10

# Create platform that ensures job b will be in submitted state for long enough
create_test_global_config '' "
[platforms]
    [[old_street]]
        job runner = at
        job runner command template = at now + 5 minutes
        hosts = localhost
        install target = localhost
"

install_and_validate
reftest_run

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-a" \
    "[1/a/01(flows=none):failed(held)] job killed" -F

J_LOG_A="${WORKFLOW_RUN_DIR}/log/job/1/a/NN/job-activity.log"
# Failed handler should not run:
grep_fail "[(('event-handler-00', 'failed'), 1) out]" "$J_LOG_A" -F
# (Check submitted handler as a control):
grep_ok "[(('event-handler-00', 'submitted'), 1) out]" "$J_LOG_A" -F

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-b" \
    "[1/b/01(flows=none):submit-failed(held)] job killed" -F

J_LOG_B="${WORKFLOW_RUN_DIR}/log/job/1/b/NN/job-activity.log"
grep_fail "[(('event-handler-00', 'submission failed'), 1) out]" "$J_LOG_B" -F
grep_ok "[(('event-handler-00', 'submitted'), 1) out]" "$J_LOG_B" -F

# Check task state updated in DB despite removal from task pool:
sqlite3 "${WORKFLOW_RUN_DIR}/.service/db" \
    "SELECT status, flow_nums FROM task_states WHERE name='a';" > task_states.out
cmp_ok task_states.out - <<< "failed|[]"
# Check job updated in DB:
sqlite3 "${WORKFLOW_RUN_DIR}/.service/db" \
    "SELECT run_status, time_run_exit FROM task_jobs WHERE cycle='1' AND name='a';" > task_jobs.out
cmp_ok_re task_jobs.out - <<< "1\|[\w:+-]+"

purge
