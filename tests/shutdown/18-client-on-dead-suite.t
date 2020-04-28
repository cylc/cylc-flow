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
# Test suite shuts down with error on missing contact file
# And correct behaviour with client on the next 2 connection attempts.
. "$(dirname "$0")/test_header"
set_test_number 3
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        abort on stalled = True
        abort on inactivity = True
        inactivity = PT3M
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
cylc run --hold --no-detach "${SUITE_NAME}" 1>'cylc-run.out' 2>&1 &
MYPID=$!
poll_suite_running
kill "${MYPID}"  # Should leave behind the contact file
wait "${MYPID}" 1>'/dev/null' 2>&1 || true
run_fail "${TEST_NAME_BASE}-1" cylc ping "${SUITE_NAME}"
contains_ok "${TEST_NAME_BASE}-1.stderr" <<__ERR__
SuiteStopped: ${SUITE_NAME} is not running
__ERR__
purge_suite "${SUITE_NAME}"
exit
