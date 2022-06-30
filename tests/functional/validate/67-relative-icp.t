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

# Checking that syntax of relative initial cycle point is validated.
# Note: remember to update this test after 01/01/2117

. "$(dirname "$0")/test_header"
set_test_number 3

cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduler]
    UTC mode = true
    allow implicit tasks = True
[scheduling]
    initial cycle point = previous(-17T1200Z; -18T1200Z) - P1D
    [[graph]]
        P1D = t1
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val" cylc validate .

TEST_NAME="${TEST_NAME_BASE}-graph"
run_ok "$TEST_NAME" cylc graph --reference .
grep_ok "20171231T1200Z/t1" "${TEST_NAME}.stdout"

exit
