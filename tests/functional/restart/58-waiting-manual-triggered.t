#!/bin/bash
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
# Test that a task manually triggered just before shutdown will run on restart.

. "$(dirname "$0")/test_header"

set_test_number 6

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"

DB_FILE="${WORKFLOW_RUN_DIR}/log/db"

# It should have shut down with 2/foo waiting with the is_manual_submit flag on.
TEST_NAME="${TEST_NAME_BASE}-db-task-states"
QUERY='SELECT status, is_manual_submit FROM task_states WHERE cycle IS 2;'
run_ok "$TEST_NAME" sqlite3 "$DB_FILE" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" << '__EOF__'
waiting|1
__EOF__

# It should restart and shut down normally, not stall with 2/foo waiting on 1/foo.
workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play --no-detach "${WORKFLOW_NAME}"

# Check that 2/foo job 02 did run before shutdown.
grep_workflow_log_ok "${TEST_NAME_BASE}-grep" "\[2\/foo\/02:running\] => succeeded"

purge
exit
