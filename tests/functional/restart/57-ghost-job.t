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
# Test restarting when there is a "ghost job" in the DB (has a submit_time in
# task_jobs table but no submit_exit_time or run_time)

. "$(dirname "$0")/test_header"
set_test_number 9

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
mkdir "${WORKFLOW_RUN_DIR}/.service"
DB_PATH="${WORKFLOW_RUN_DIR}/.service/db"
sqlite3 "$DB_PATH" < db.sqlite3

query_db_task_jobs() {
    TEST_NAME="$1"
    sqlite3 "$DB_PATH" \
        'SELECT cycle, name, submit_num FROM task_jobs' > "${TEST_NAME}.stdout"
}

get_submit_time() {
    sqlite3 "$DB_PATH" 'SELECT time_submit FROM task_jobs'
}

# cylc client input stored as var:
read -r -d '' gqlQuery << _args_
{
  "request_string": "
query {
  workflows(ids: [\"${WORKFLOW_NAME}\"]) {
    jobs {
      cyclePoint, name, submitNum
    }
  }
}"
}
_args_

# -----------------------------------------------------------------------------

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play --upgrade -vv "${WORKFLOW_NAME}" --pause

# There will be 1 ghost job in DB:
TEST_NAME="${TEST_NAME_BASE}-db-query-1"
query_db_task_jobs "$TEST_NAME"
cmp_ok "${TEST_NAME}.stdout" << EOF
1|foo|1
EOF

# Get submit time for that job:
orig_submit_time="$(get_submit_time)"

# Ghost job should not be in data store:
TEST_NAME="${TEST_NAME_BASE}-datastore-query-1"

run_graphql_ok "$TEST_NAME" "$WORKFLOW_NAME" "$gqlQuery"

cmp_json "${TEST_NAME}-cmp" "${TEST_NAME}.stdout" << EOF
{
    "workflows": [{
        "jobs": []
    }]
}
EOF

workflow_run_ok "${TEST_NAME_BASE}-resume" cylc play --upgrade "${WORKFLOW_NAME}"
poll_workflow_stopped

# Job should have been replaced in DB with same submit num:
TEST_NAME="${TEST_NAME_BASE}-db-query-2"
query_db_task_jobs "$TEST_NAME"

cmp_ok "${TEST_NAME}.stdout" << EOF
1|foo|1
EOF

# Submit time should be different however:
TEST_NAME="${TEST_NAME_BASE}-submit-time-cmp"
if [[ "$(get_submit_time)" != "$orig_submit_time" ]]; then
    ok "$TEST_NAME"
else
    fail "$TEST_NAME" \
        "Expected time_submit in task_jobs table to be different from original"
fi

# Job should be in data store:
TEST_NAME="${TEST_NAME_BASE}-datastore-query-2"
cmp_json "${TEST_NAME}-cmp" "${WORKFLOW_RUN_DIR}/work/1/foo/gqlResponse.json" << EOF
{
    "workflows": [{
        "jobs": [{
            "cyclePoint": "1",
            "name": "foo",
            "submitNum": 1
        }]
    }]
}
EOF

purge
