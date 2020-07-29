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
# Test saving of cycle point time zone for restart, which is important for
# restarting a suite after e.g. a daylight saving change

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
        'SELECT * FROM suite_params WHERE key=="cp_tz";' > 'dump.out'
}

set_test_number 5

init_suite "${TEST_NAME_BASE}" << '__SUITERC__'
[cylc]
    UTC mode = False
[scheduling]
    initial cycle point = now
    [[special tasks]]
        clock-trigger = foo(PT0M)
    [[graph]]
        T23 = foo
[runtime]
    [[foo]]
        script = true
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Set time zone to +01:00
export TZ=BST-1

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}"
dumpdbtables
cmp_ok 'dump.out' <<< 'cp_tz|+0100'

cylc stop "${SUITE_NAME}"

# Simulate DST change
export TZ=UTC

suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart "${SUITE_NAME}"
dumpdbtables
cmp_ok 'dump.out' <<< 'cp_tz|+0100'

cylc stop "${SUITE_NAME}"

purge_suite "${SUITE_NAME}"
exit
