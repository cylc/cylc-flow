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
# Test restart with ignore stop point

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="stopcp";' >'stopcp.out'
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' >'taskpool.out'
}

set_test_number 7

# Event should look like this:
# Start suite with stop point = 2018
# Request suite stop while at 2015
# Restart, ignoring stop point
# Suite runs to final cycle point == 2020
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    UTC mode=True
    cycle point format = %Y
    [[events]]
        abort on stalled = True
        abort on inactivity = True
        inactivity = P1M
[scheduling]
    initial cycle point = 2015
    final cycle point = 2020
    [[graph]]
        P1Y = t1[-P1Y] => t1
[runtime]
    [[t1]]
        script = """
case "${CYLC_TASK_CYCLE_POINT}" in
2015)
    cylc stop "${CYLC_SUITE_NAME}"
    :;;
esac
"""
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" --no-detach --stop-point=2018
dumpdbtables
cmp_ok 'stopcp.out' <<<'stopcp|2018'
cmp_ok 'taskpool.out' <<'__OUT__'
2016|t1|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc restart "${SUITE_NAME}" --no-detach --ignore-stop-cycle-point
dumpdbtables
cmp_ok 'stopcp.out' <'/dev/null'
cmp_ok 'taskpool.out' <'/dev/null'

purge_suite "${SUITE_NAME}"
exit
