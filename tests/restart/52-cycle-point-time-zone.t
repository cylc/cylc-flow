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
# Test saving and loading of cycle point time zone to/from database on a run
# followed by a restart. Important for restarting a suite after a system
# time zone change.

. "$(dirname "$0")/test_header"

set_test_number 7

init_suite "${TEST_NAME_BASE}" << '__FLOW__'
[cylc]
    UTC mode = False
[scheduling]
    initial cycle point = now
    [[dependencies]]
        [[[T23]]]
            graph = stopper
[runtime]
    [[stopper]]
        script = cylc stop "$CYLC_SUITE_NAME"
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

# Set time zone to +02:15
export TZ=XXX-02:15

suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --no-detach

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT * FROM suite_params WHERE key=="cycle_point_tz" OR key=="UTC_mode";' > 'dump.out'
cmp_ok 'dump.out' << __EOF__
UTC_mode|0
cycle_point_tz|+0215
__EOF__

# Simulate DST change
export TZ=UTC

suite_run_ok "${TEST_NAME_BASE}-restart" cylc restart "${SUITE_NAME}" --no-detach

log_scan "${TEST_NAME_BASE}-log-scan" "${SUITE_RUN_DIR}/log/suite/log" 1 0 \
    'LOADING suite parameters' \
    '+ UTC mode = False' \
    '+ cycle point time zone = +0215'

purge_suite "${SUITE_NAME}"
exit
