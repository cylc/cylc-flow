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
# Test log rolling.

. "$(dirname "$0")/test_header"
set_test_number 11
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        abort on stalled = True
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    final cycle point = 20
    [[graph]]
        P1 = t1 & t2 & t3
[runtime]
    [[t1, t2, t3]]
        script = true
__SUITERC__

create_test_globalrc '' '
[suite logging]
    rolling archive length = 8
    maximum size in bytes = 2048'
run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach "${SUITE_NAME}"
FILES="$(ls "${HOME}/cylc-run/${SUITE_NAME}/log/suite/log."*)"
run_ok "${TEST_NAME_BASE}-n-logs" test 8 -eq "$(wc -l <<<"${FILES}")"
for FILE in ${FILES}; do
    run_ok "${TEST_NAME_BASE}-log-size" test "$(stat -c'%s' "${FILE}")" -le 2048
done

purge_suite "${SUITE_NAME}"
exit
