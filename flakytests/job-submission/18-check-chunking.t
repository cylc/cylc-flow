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
# Test that a job containing more than 100 tasks will split into batches.

. "$(dirname "$0")/test_header"
set_test_number 3

create_test_globalrc '' '
process pool size = 1
'

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        abort on inactivity = True
        abort on stalled = True
        inactivity = PT10M
    [[parameters]]
        p = 1..202
[scheduling]
    [[graph]]
        R1 = t1<p>
[runtime]
    [[t1<p>]]
        # Reduce the load on many jobs sending the "started" message
        init-script = """
sleep $((RANDOM % 10))
"""
        script = """
wait
sleep $((RANDOM % 5))
"""
__SUITERC__


run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"
grep_ok "# will invoke in batches, sizes=\[68, 68, 66\]" \
    "${SUITE_RUN_DIR}/log/suite/log"

# tidy up
purge_suite "${SUITE_NAME}"
exit
