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
#------------------------------------------------------------------------------
# Test job submission with a very chatty command.
# + Simulate "cylc jobs-submit" getting killed half way through.

export REQUIRE_PLATFORM='runner:at'

. "$(dirname "$0")/test_header"
set_test_number 15

# This test relies on jobs inheriting the scheduler environment: the job
# submission command bin/talkingnonsense reads COPYING from $CYLC_REPO_DIR
# and writes to $CYLC_WORKFLOW_RUN_DIR.

create_test_global_config "
[scheduler]
    process pool timeout = PT10S
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        job runner command template = talkingnonsense %(job)s
        clean job submission environment = False
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-workflow-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# Logged killed jobs-submit command
cylc cat-log "${WORKFLOW_NAME}" | sed -n '
/\[jobs-submit \(cmd\|ret_code\|out\|err\)\]/,+2{
    s/^.*\(\[jobs-submit\)/\1/p
}' >'log'
contains_ok 'log' <<'__OUT__'
[jobs-submit ret_code] -9
[jobs-submit err] killed on timeout (PT10S)
__OUT__

# Logged jobs that called talkingnonsense
sed -n 's/\(\[jobs-submit out\]\) .*\(|1\/\)/\1 \2/p' 'log' >'log2'
N=0
while read -r; do
    TAIL="${REPLY#"${WORKFLOW_RUN_DIR}"/log/job/}"
    TASK_JOB="${TAIL%/job}"
    contains_ok 'log2' <<<"[jobs-submit out] |${TASK_JOB}|1|None"
    ((N += 1))
done <"${WORKFLOW_RUN_DIR}/talkingnonsense.out"
# Logged jobs that did not call talkingnonsense
for I in $(eval echo "{$N..9}"); do
    contains_ok 'log2' <<<"[jobs-submit out] |1/nh${I}/01|1"
done

# Task pool in database contains the correct states
TEST_NAME="${TEST_NAME_BASE}-db-task-pool"
DB_FILE="${WORKFLOW_RUN_DIR}/log/db"
QUERY='SELECT cycle, name, status, is_held FROM task_pool'
run_ok "$TEST_NAME" sqlite3 "$DB_FILE" "$QUERY"
sort "${TEST_NAME}.stdout" > "${TEST_NAME}.stdout.sorted"
cmp_ok "${TEST_NAME}.stdout.sorted" << '__OUT__'
1|nh0|submit-failed|0
1|nh1|submit-failed|0
1|nh2|submit-failed|0
1|nh3|submit-failed|0
1|nh4|submit-failed|0
1|nh5|submit-failed|0
1|nh6|submit-failed|0
1|nh7|submit-failed|0
1|nh8|submit-failed|0
1|nh9|submit-failed|0
__OUT__

purge
exit
