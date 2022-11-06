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
# Test restarting a simple workflow with a broadcast
if [[ -z ${TEST_DIR:-} ]]; then
    . "$(dirname "$0")/test_header"
fi
#-------------------------------------------------------------------------------
set_test_number 8
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" 'broadcast'
cp "$TEST_SOURCE_DIR/lib/flow-runtime-restart.cylc" "${WORKFLOW_RUN_DIR}/"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stderr" <'/dev/null'
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach --abort-if-any-task-fails "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-restart-run"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach --abort-if-any-task-fails "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
grep_ok "send_a_broadcast_task|20130923T0000Z|1|1|succeeded" \
    "${WORKFLOW_RUN_DIR}/pre-restart-db"
contains_ok "${WORKFLOW_RUN_DIR}/post-restart-db" <<'__DB_DUMP__'
send_a_broadcast_task|20130923T0000Z|1|1|succeeded
shutdown|20130923T0000Z|1|1|succeeded
__DB_DUMP__
"${WORKFLOW_RUN_DIR}/bin/ctb-select-task-states" "${WORKFLOW_RUN_DIR}" \
    > "${TEST_DIR}/db"
contains_ok "${TEST_DIR}/db" <<'__DB_DUMP__'
broadcast_task|20130923T0000Z|1|1|succeeded
finish|20130923T0000Z|1|1|succeeded
output_states|20130923T0000Z|1|1|succeeded
send_a_broadcast_task|20130923T0000Z|1|1|succeeded
shutdown|20130923T0000Z|1|1|succeeded
__DB_DUMP__
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" '
    SELECT
        point,namespace,key,value
    FROM
        broadcast_states
    ORDER BY
        point,namespace,key' >'select-broadcast-states.out'
cmp_ok 'select-broadcast-states.out' \
    <<<"20130923T0000Z|broadcast_task|[environment]MY_VALUE|'something'"
#-------------------------------------------------------------------------------
purge
