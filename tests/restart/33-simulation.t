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
# Test cylc/cylc-flow#2788
. "$(dirname "$0")/test_header"

set_test_number 3
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    cycle point format = %Y
    [[events]]
        abort if any task fails = True
        abort on stalled = True
[scheduling]
    initial cycle point = 2018
    [[graph]]
        P1Y = t1
[runtime]
    [[t1]]
        script = true
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --no-detach --until=2019 --mode=simulation "${SUITE_NAME}"
# Force a waiting task into a running task
sqlite3 "${HOME}/cylc-run/${SUITE_NAME}/.service/db" \
    'UPDATE task_states SET status="running" WHERE name=="t1" AND cycle=="2019"'
sqlite3 "${HOME}/cylc-run/${SUITE_NAME}/.service/db" \
    'UPDATE task_pool SET status="running" WHERE name=="t1" AND cycle=="2019"'
suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart --debug --no-detach --until=2020 --mode=simulation "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
