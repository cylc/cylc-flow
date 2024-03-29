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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test validation with initial and final cycle points in scheduling but no R1.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduling]
    initial cycle point = 2015-01-01
    final cycle point = 2015-01-01
    [[graph]]
        1 = foo

[runtime]
    [[foo]]
    script = sleep 10
__FLOW_CONFIG__
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}"
run_fail "${TEST_NAME}" cylc validate -v .
grep_ok "WorkflowConfigError: Cannot process recurrence 1" "${TEST_NAME}.stderr"
#-------------------------------------------------------------------------------
exit
