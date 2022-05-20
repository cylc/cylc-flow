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
# Test restarting with a task waiting to retry (was retrying state).
. "$(dirname "$0")/test_header"
set_test_number 8
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
        abort on inactivity timeout = True
        inactivity timeout = PT3M
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = """
            cylc__job__wait_cylc_message_started
            if ((CYLC_TASK_TRY_NUMBER < 3)); then
                exit 1
            elif ((CYLC_TASK_TRY_NUMBER == 3)); then
                cylc stop "${CYLC_WORKFLOW_ID}"
                exit 1
            fi
        """
        [[[job]]]
            execution retry delays = 3*PT0S
__FLOW_CONFIG__

#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" 'SELECT cycle, name, status FROM task_pool' >'sqlite3.out'
cmp_ok 'sqlite3.out' <<'__DB_DUMP__'
1|t1|waiting
__DB_DUMP__


workflow_run_ok "${TEST_NAME_BASE}-restart-pause" \
    cylc play --debug --pause "${WORKFLOW_NAME}"

# query jobs
TEST_NAME="${TEST_NAME_BASE}-jobs-query"

read -r -d '' jobsQuery <<_args_
{
  "request_string": "
query {
  jobs (sort: {keys: [\"submitNum\"]}) {
    state
    submitNum
  }
}",
  "variables": null
}
_args_

run_graphql_ok "${TEST_NAME}" "${WORKFLOW_NAME}" "${jobsQuery}"

cmp_json "${TEST_NAME}-out" "${TEST_NAME_BASE}-jobs-query.stdout" << __HERE__
{
    "jobs": [
        {
            "state": "failed",
            "submitNum": 1
        },
        {
            "state": "failed",
            "submitNum": 2
        },
        {
            "state": "failed",
            "submitNum": 3
        }
    ]
}
__HERE__

# stop workflow
cylc stop --max-polls=10 --interval=2 "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-restart-resume" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'sqlite3.out'
cmp_ok 'sqlite3.out' </dev/null
#-------------------------------------------------------------------------------
purge
exit
