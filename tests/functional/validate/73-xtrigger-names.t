#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
# Test validating xtrigger names in workflow.
. "$(dirname "$0")/test_header"

set_test_number 3

TEST_NAME="${TEST_NAME_BASE}-val"

# test a valid xtrigger
cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduling]
    initial cycle point = 2000
    [[xtriggers]]
        foo = wall_clock():PT1S
    [[graph]]
        R1 = @foo => bar
[runtime]
    [[bar]]
__FLOW_CONFIG__
run_ok "${TEST_NAME}-valid" cylc validate flow.cylc

# test an invalid xtrigger
cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduling]
    initial cycle point = 2000
    [[xtriggers]]
        foo-1 = wall_clock():PT1S
    [[graph]]
            R1 = @foo-1 => bar
[runtime]
    [[bar]]
__FLOW_CONFIG__

run_fail "${TEST_NAME}-invalid" cylc validate flow.cylc
grep_ok 'Invalid xtrigger name' "${TEST_NAME}-invalid.stderr"

exit
