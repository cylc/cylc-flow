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
# Test restart with stop point

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="stopcp";' >'stopcp.out'
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' >'taskpool.out'
}

set_test_number 16

# Event should look like this:
# Start suite with stop point = 2018
# Request suite stop while at 2015
# Restart
# Reload suite at 2016, modify final cycle point from 2024 to 2025
# Suite runs to stop point == 2018, reset stop point before stop
# Restart
# Set suite stop point == 2021, while at 2019
# Request suite stop right after, should retain stop point == 2021
# Restart, should run to 2021, reset stop point before stop
# Restart, should run to final cycle point == 2025
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
    final cycle point = 2024
    [[graph]]
        P1Y = t1[-P1Y] => t1
[runtime]
    [[t1]]
        script = """
case "${CYLC_TASK_CYCLE_POINT}" in
2015)
    cylc stop "${CYLC_SUITE_NAME}"
    :;;
2016)
    sed -i 's/\(final cycle point =\) 2024/\1 2025/' "${CYLC_SUITE_DEF_PATH}/suite.rc"
    cylc reload "${CYLC_SUITE_NAME}"
    cylc__job__poll_grep_suite_log "Reload completed"
    :;;
2019)
    cylc stop "${CYLC_SUITE_NAME}" '2021'
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
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stopcp.out' <'/dev/null'
cmp_ok 'taskpool.out' <<'__OUT__'
2019|t1|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stopcp.out' <<<'stopcp|2021'
cmp_ok 'taskpool.out' <<'__OUT__'
2020|t1|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-3" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stopcp.out' <'/dev/null'
cmp_ok 'taskpool.out' <<'__OUT__'
2022|t1|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-4" \
    cylc restart "${SUITE_NAME}" --no-detach
dumpdbtables
cmp_ok 'stopcp.out' <'/dev/null'
cmp_ok 'taskpool.out' <'/dev/null'

purge_suite "${SUITE_NAME}"
exit
