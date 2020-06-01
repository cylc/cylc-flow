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
# Test for ISODATETIMEREF and ISODATETIMECALENDAR.
. "$(dirname "${0}")/test_header"
set_test_number 2

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[cylc]
    UTC mode = True
    [[events]]
        abort on stalled = True
[scheduling]
    initial cycle point = 20200202T2020Z
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = """
test "${ISODATETIMECALENDAR}" = "${CYLC_CYCLING_MODE}"
test "${ISODATETIMECALENDAR}" = 'gregorian'
test "${ISODATETIMEREF}" = "${CYLC_TASK_CYCLE_POINT}"
test "${ISODATETIMEREF}" = '20200202T2020Z'
"""
__SUITE_RC__

suite_run_ok "${TEST_NAME_BASE}" cylc run --no-detach "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[cylc]
    UTC mode = True
    [[events]]
        abort on stalled = True
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = """
test -z "${ISODATETIMECALENDAR:-}"
test -z "${ISODATETIMEREF:-}"
"""
__SUITE_RC__
suite_run_ok "${TEST_NAME_BASE}" cylc run --no-detach "${SUITE_NAME}"

purge_suite "${SUITE_NAME}"
exit
