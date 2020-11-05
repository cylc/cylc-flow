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
# Test saving and loading of cycle point time zone to/from database on a run
# followed by a restart. Important for restarting a suite after a system
# time zone change.

. "$(dirname "$0")/test_header"

set_test_number 7

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"


run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --stop-point=2
poll_suite_stopped

DB_FILE="${SUITE_RUN_DIR}/log/db"

# Check task_prerequisites table:
TEST_NAME="${TEST_NAME_BASE}-db-task-prereq"
QUERY='SELECT * FROM task_prerequisites ORDER BY cycle, name, prereq_cycle;'
run_ok "$TEST_NAME" sqlite3 "$DB_FILE" "$QUERY"
cmp_ok "${TEST_NAME}.stdout" << '__EOF__'
2|bar|foo|1|succeeded|0
2|bar|apollo|2|The Eagle has landed|satisfied naturally
3|bar|foo|2|succeeded|satisfied naturally
3|bar|apollo|3|The Eagle has landed|0
__EOF__

suite_run_ok "${TEST_NAME_BASE}-restart" cylc restart "${SUITE_NAME}" --stop-point=3
poll_suite_stopped

# Check bar.2 is still waiting (i.e. prereqs not satisfied):
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
