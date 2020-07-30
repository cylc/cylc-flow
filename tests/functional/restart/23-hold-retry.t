#!/usr/bin/env bash
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
# Test restart with held (retrying) task
. "$(dirname "$0")/test_header"
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name' >'task-pool.out'
cmp_ok 'task-pool.out' <<__OUT__
1|t1|retrying
__OUT__
cylc restart "${SUITE_NAME}" --debug --no-detach 1>'out' 2>&1 &
SUITE_PID=$!
poll_grep_suite_log -F 'INFO - + t1.1 retrying (held)'
run_ok "${TEST_NAME_BASE}-release" cylc release "${SUITE_NAME}"
poll_grep_suite_log -F 'INFO - DONE'
if ! wait "${SUITE_PID}"; then
    cat 'out' >&2
fi
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT * FROM task_pool ORDER BY cycle, name' >'task-pool.out'
cmp_ok 'task-pool.out' </dev/null

purge_suite "${SUITE_NAME}"
exit
