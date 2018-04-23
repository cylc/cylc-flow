#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Test upgrade of 7.6.X database on restart.
# Focus on migration from pickle to json for task action timer data.
. "$(dirname "$0")/test_header"

which sqlite3 > '/dev/null' || skip_all "sqlite3 not installed?"
set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Load database dump created from a 7.6.X suite
mkdir -p "${SUITE_RUN_DIR}"
sqlite3 "${SUITE_RUN_DIR}/.service/db" <'db.dump'

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}-restart" \
    cylc restart --debug --no-detach "${SUITE_NAME}"
# Check that the schema for task_action_timers table is upgraded
sqlite3 "${SUITE_RUN_DIR}/log/db" '.schema task_action_timers' \
    >'task_action_timers.schema'
cmp_ok 'task_action_timers.schema' \
    <<<'CREATE TABLE task_action_timers(cycle TEXT, name TEXT, ctx_key TEXT, ctx TEXT, delays TEXT, num INTEGER, delay TEXT, timeout TEXT, PRIMARY KEY(cycle, name, ctx_key));'
# Check that the content for task_action_timers table is upgraded
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT * FROM task_action_timers ORDER BY cycle, name, ctx_key;' \
    >'db-select.out'
cmp_ok 'db-select.out' <<'__OUT__'
1|t1|["try_timers", "retrying"]|null|[60.0]|0||
1|t1|["try_timers", "submit-retrying"]|null|[]|0||
1|t1|[["event-handler-00", "submission failed"], 1]|["CustomTaskEventHandlerContext", [["event-handler-00", "submission failed"], "event-handler", "false 'submission failed' 'foo' 't1.1' 'job submission failed'"]]|[60.0, 60.0]|1||
__OUT__

purge_suite "${SUITE_NAME}"
exit
