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
# Test restart with ignore final point

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="fcp";' >'fcp.out'
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' >'taskpool.out'
}

set_test_number 13

# Event should look like this:
# Start suite with final point = 2018
# Request suite stop while at 2015
# Restart
# Suite runs to final cycle point == 2018
# Restart
# Suite stop immediately
# Restart, ignore final cycle point
# Suite runs to final cycle point == 2020
# TODO SOD - LAST TEST FAILS BECAUSE WE DON'T SPAWN PAST THE (original 2018) FCP
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
    cylc run "${SUITE_NAME}" --no-detach --fcp=2018
dumpdbtables
cmp_ok 'fcp.out' <<<'fcp|2018'
cmp_ok 'taskpool.out' <<'__OUT__'
2016|t1|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'fcp.out' <<<'fcp|2018'
cmp_ok 'taskpool.out' <'/dev/null'

suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'fcp.out' <<<'fcp|2018'
cmp_ok 'taskpool.out' <'/dev/null'

# TODO - UNDER SOD THE PREVIOUS STOP POINT CAN'T BE OVERRIDDEN ON RESTART
# UNLESS WE SPAWN INTO THE RUNAHEAD POOL BEYOND THE STOP POINT (PROBABLY A GOOD
# IDEA - MAKES HANDLED FOR FCP SAME AS AN EARLER STOP POINT).
suite_run_ok "${TEST_NAME_BASE}-restart-3" \
    cylc restart "${SUITE_NAME}" --no-detach --ignore-final-cycle-point
dumpdbtables
cmp_ok 'fcp.out' <'/dev/null'
cmp_ok 'taskpool.out' <'/dev/null'

purge_suite "${SUITE_NAME}"
exit
