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
# Test restart with held (waiting) task
. "$(dirname "$0")/test_header"
set_test_number 8
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --debug --no-detach
# Check task pool
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT cycle, name, status FROM task_pool WHERE is_held==1 ORDER BY cycle, name' \
    >'task_pool-1.out'
cmp_ok 'task_pool-1.out' << __EOF__
2016|t2|waiting
__EOF__
# Check tasks_to_hold table
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT cycle, name FROM tasks_to_hold ORDER BY cycle, name' \
    > 'tasks_to_hold-1.out'
cmp_ok 'tasks_to_hold-1.out' << __EOF__
2016|t2
2017|t2
__EOF__

workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play "${WORKFLOW_NAME}" --debug --no-detach
grep_ok 'INFO - + t2\.2016 waiting (held)' "${WORKFLOW_RUN_DIR}/log/workflow/log"
# Check task pool
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT * FROM task_pool' >'task_pool-end.out'
cmp_ok 'task_pool-end.out' </dev/null
# Check tasks_to_hold table
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT * FROM tasks_to_hold' > 'tasks_to_hold-end.out'
cmp_ok 'tasks_to_hold-end.out' < /dev/null

purge
exit
