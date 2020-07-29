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
# Test restart with held suite
. "$(dirname "$0")/test_header"
set_test_number 7
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --debug --no-detach

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT value FROM suite_params WHERE key=="is_held"' >'suite-is-held.out'
cmp_ok 'suite-is-held.out' <<<'1'
T1_2016_PID="$(sed -n 's/CYLC_JOB_PID=//p' "${SUITE_RUN_DIR}/log/job/2016/t1/01/job.status")"
poll_pid_done "${T1_2016_PID}"

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle, name, status FROM task_pool WHERE is_held IS 1 ORDER by cycle, name' >'suite-stopped.out'
cmp_ok 'suite-stopped.out' <<'__OUT__'
2016|t2|waiting
2017|t1|waiting
__OUT__

cylc restart "${SUITE_NAME}" --debug --no-detach 1>"${TEST_NAME_BASE}-restart.out" 2>&1 &
CYLC_RESTART_PID=$!
# Ensure suite has started
poll_suite_running
cylc release "${SUITE_NAME}" 't2.2016'
poll_grep 'CYLC_JOB_EXIT' "${SUITE_RUN_DIR}/log/job/2016/t2/01/job.status"

cylc release "${SUITE_NAME}"
cylc poll "${SUITE_NAME}"
# Ensure suite has completed
run_ok "${TEST_NAME_BASE}-restart" wait "${CYLC_RESTART_PID}"

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT value FROM suite_params WHERE key=="is_held"' >'suite-is-held.out'
cmp_ok 'suite-is-held.out' <'/dev/null'
# Should shut down with emtpy task pool.
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name' >'task-pool.out'
cmp_ok 'task-pool.out' <<'__OUT__'
__OUT__
purge_suite "${SUITE_NAME}"
exit
