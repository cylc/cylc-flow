#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

set_test_number 2

init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[parameters]]
        p = 1..202
[scheduling]
    [[dependencies]]
        graph = t1<p>
[runtime]
    [[t1<p>]]
        script = """
wait
sleep $((RANDOM % 5))
"""
__SUITERC__


TEST_NAME=${TEST_NAME_BASE}-run
run_ok $TEST_NAME cylc run --debug --no-detach $SUITE_NAME
LOG_FILE=$(cylc cat-log $SUITE_NAME -m p)

TEST_NAME=${TEST_NAME_BASE}-itasks-msg
grep_ok "# will invoke in batches, sizes=\[68, 68, 66\]" $LOG_FILE

# tidy up
purge_suite $SUITE_NAME

