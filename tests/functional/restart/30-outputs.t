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
# Test task outputs status is retained on restart
# TODO SoD: this is no longer a restart test (the original was based on
#   stalling with a task waiting on the other output)
# Now it tests that the right thing happens with mutually exclusive outputs.
. "$(dirname "$0")/test_header"

set_test_number 4
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    "SELECT outputs FROM task_outputs WHERE name IS 't1'" >'sqlite3.out'
cmp_json 'sqlite3.out' 'sqlite3.out' <<<'{"submitted": "submitted", "started": "started", "succeeded": "succeeded", "hello": "hi there"}'

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task-pool.out'
cmp_ok 'task-pool.out' <'/dev/null'

purge
exit
