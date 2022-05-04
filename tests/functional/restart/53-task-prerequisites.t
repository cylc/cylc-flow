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
# Test custom task prerequisites and the task_prerequisites DB table work as
# expected

. "$(dirname "$0")/test_header"

set_test_number 7

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_fail "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --stopcp=2 --no-detach

DB_FILE="${WORKFLOW_RUN_DIR}/log/db"

# Check task_prerequisites table:
TEST_NAME="${TEST_NAME_BASE}-db-task-prereq"
QUERY='SELECT * FROM task_prerequisites ORDER BY cycle, name, prereq_cycle;'
run_ok "$TEST_NAME" sqlite3 "$DB_FILE" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" << '__EOF__'
1|bar|[1]|foo|0|succeeded|satisfied naturally
1|bar|[1]|apollo|1|The Eagle has landed|satisfied naturally
2|bar|[1]|foo|1|succeeded|0
2|bar|[1]|apollo|2|The Eagle has landed|satisfied naturally
3|bar|[1]|foo|2|succeeded|satisfied naturally
3|bar|[1]|apollo|3|The Eagle has landed|0
__EOF__

workflow_run_fail "${TEST_NAME_BASE}-restart" cylc play "${WORKFLOW_NAME}" --stopcp=3 --no-detach

# Check 2/bar is still waiting (i.e. prereqs not satisfied):
TEST_NAME="${TEST_NAME_BASE}-db-task-pool"
QUERY='SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;'
run_ok "$TEST_NAME" sqlite3 "$DB_FILE" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" << '__EOF__'
1|foo|failed
2|bar|waiting
4|apollo|waiting
4|bar|waiting
4|foo|waiting
__EOF__

purge
exit
