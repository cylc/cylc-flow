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
# Test restart with stop task

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="stop_task";' >'stoptask.out'
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' >'taskpool.out'
}

set_test_number 10

# Event should look like this:
# Start suite
# At t1.1, set stop task to t5.1
# At t2.1, stop suite at t2.1
# Restart
# Suite runs to stop task t5.1, reset stop task.
# Restart
# Suite stops normally at t8.1
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[parameters]]
        i = 1..8
    [[events]]
        abort on stalled = True
        abort on inactivity = True
        inactivity = P1M
[scheduling]
    [[graph]]
        R1 = t<i-1> => t<i>
[runtime]
    [[t<i>]]
        script = true
    [[t<i=1>]]
        script = cylc stop "${CYLC_SUITE_NAME}" 't_i5.1'
    [[t<i=2>]]
        script = cylc stop "${CYLC_SUITE_NAME}"
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stoptask.out' <<<'stop_task|t_i5.1'
cmp_ok 'taskpool.out' <<'__OUT__'
1|t_i3|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stoptask.out' <'/dev/null'
cmp_ok 'taskpool.out' <<'__OUT__'
1|t_i6|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stoptask.out' <'/dev/null'
cmp_ok 'taskpool.out' <'/dev/null'

purge_suite "${SUITE_NAME}"
exit
