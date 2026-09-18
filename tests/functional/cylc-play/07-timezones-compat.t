#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) Earth Sciences New Zealand & British Crown (Met Office)
# & Contributors.
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
#------------------------------------------------------------------------
# Test for Timezone = Z
# TODO remove deprecated suite.rc section at Cylc 8.x

. "$(dirname "$0")/test_header"

set_test_number 2

# integer cycling

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    initial cycle point = 1000
    [[graph]]
        R1 = foo
__FLOW_CONFIG__

cylc install --no-run-name --workflow-name="${WORKFLOW_NAME}-foo"

# Pick a deliberately peculier timezone;
export TZ=Australia/Eucla

run_ok "${TEST_NAME_BASE}" cylc play "${WORKFLOW_NAME}-foo" --no-detach --timestamp
grep_ok "+08:45 INFO" "${TEST_NAME_BASE}.stderr"

purge

exit
