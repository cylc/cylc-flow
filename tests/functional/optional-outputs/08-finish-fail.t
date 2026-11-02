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

#-------------------------------------------------------------------------
# Test handling of failed tasks in finish triggers.

. "$(dirname "$0")/test_header"
set_test_number 3

# When a task with a finish trigger fails:
#   No runahead stall and no stall at final cycle point, because finish
#   triggers imply success is optional (i.e. no incomplete tasks created).

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CYLC__'
[scheduler]
    [[events]]
        stall timeout = PT0S
        abort on stall timeout = True
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    final cycle point = 2
    runahead limit = P0
    [[dependencies]]
        [[[P1]]]
            graph = "foo:finish"
[runtime]
    [[foo]]
        script = false
__FLOW_CYLC__


# Validate with a deprecation message
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

grep_ok "graph items were automatically upgraded" "${TEST_NAME}.stderr"

# No stall expected.
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach --debug "${WORKFLOW_NAME}"

purge
