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
# Test restart with override to reverse no auto shutdown setting in suite.rc

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="no_auto_shutdown";' \
        >'noautoshutdown.out'
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' >'taskpool.out'
}

set_test_number 8

# Event should look like this:
# Suite configured with: disable automatic shutdown = True
# Start suite with auto shutdown enabled
# At t2.1, stop suite
# Restart, should retain auto shutdown enabled option
# Suite runs to final task and shuts down normally
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    disable automatic shutdown = True
    [[parameters]]
        i = 1..5
    [[events]]
        abort on stalled = True
        abort on inactivity = True
        inactivity = PT1M
[scheduling]
    [[graph]]
        R1 = t<i-1> => t<i>
[runtime]
    [[t<i>]]
        script = true
    [[t<i=2>]]
        script = cylc stop "${CYLC_SUITE_NAME}"
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" --no-detach --auto-shutdown
dumpdbtables
cmp_ok 'noautoshutdown.out' <<<"no_auto_shutdown|0"
cmp_ok 'taskpool.out' <<'__OUT__'
1|t_i3|waiting
__OUT__

suite_run_ok "${TEST_NAME_BASE}-restart-1" \
    cylc restart "${SUITE_NAME}" --no-detach --debug
dumpdbtables
cmp_ok 'noautoshutdown.out' <<<'no_auto_shutdown|0'
cut -d ' ' -f 4- "${SUITE_RUN_DIR}/log/suite/log" >'log.edited'
contains_ok 'log.edited' <<__LOG__
+ no auto shutdown = False
__LOG__
cmp_ok 'taskpool.out' <'/dev/null'

purge_suite "${SUITE_NAME}"
exit
