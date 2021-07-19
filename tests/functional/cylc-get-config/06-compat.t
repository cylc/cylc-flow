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

# Test compat following https://github.com/cylc/cylc-flow/pull/3191

. "$(dirname "$0")/test_header"

set_test_number 3

cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    initial cycle point = next(T00)
    [[dependencies]]
        [[[R1]]]
            graph = r1
        [[[R1]]]
            graph = 'r2'
        [[[ R1 ]]]
            graph = """r3"""
        [[[R1]]]
            graph = """
                r4 => r5
                r6 => r7
            """
        [[[T06, T12]]]
            graph = t1 => t2
        [[[ P1D!(01T, 11T) ]]]
            graph = t3
__FLOW_CONFIG__
run_ok "${TEST_NAME_BASE}-validate" cylc validate 'flow.cylc'
run_ok "${TEST_NAME_BASE}-dependencies" \
    cylc config --item='[scheduling][graph]' 'flow.cylc'
cmp_ok "${TEST_NAME_BASE}-dependencies.stdout" <<'__OUT__'
R1 = """
    r1
    r2
    r3
    r4 => r5
    r6 => r7
"""
T06, T12 = t1 => t2
P1D!(01T, 11T) = t3
__OUT__
exit
