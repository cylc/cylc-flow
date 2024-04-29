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
# Test execution time limit works correctly with polling intervals

. "$(dirname "$0")/test_header"
set_test_number 6

init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduling]
    [[graph]]
        R1 = nolimit & limit95M & limit1H  & limit10M & limit70S
[runtime]
    [[root]]
        script = "echo Hello"
        execution polling intervals = 3*PT30S, PT10M, PT1H
    [[nolimit]]
    [[limit95M]]
        execution time limit = PT95M
    [[limit1H]]
        execution time limit = PT1H
    [[limit10M]]
        execution time limit = PT10M
    [[limit70S]]
        execution time limit = PT70S
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

cylc play --debug "${WORKFLOW_NAME}"

poll_grep_workflow_log "INFO - DONE"

# NOTE: execution timeout polling is delayed by PT1M to let things settle
# PT10M = (3*PT3S + PT9M30S) - PT1M
grep_workflow_log_ok grep-limit10M "\[1/limit10M/01:running\] health: execution timeout=None, polling intervals=3\*PT30S,PT9M30S,PT2M,PT7M,..."
# PT60M = (3*PT3S + PT10M + PT49M30S) - PT1M
grep_workflow_log_ok grep-limit1H "\[1/limit1H/01:running\] health: execution timeout=None, polling intervals=3\*PT30S,PT10M,PT49M30S,PT2M,PT7M,..."
# PT70S = (2*PT30S + PT1M10S) - PT1M
grep_workflow_log_ok grep-limit70S "\[1/limit70S/01:running\] health: execution timeout=None, polling intervals=2\*PT30S,PT1M10S,PT2M,PT7M,..."
# PT95M = (3*PT3S + PT10M + PT1H + PT24M30S) - PT1M
grep_workflow_log_ok grep-limit95M "\[1/limit95M/01:running\] health: execution timeout=None, polling intervals=3\*PT30S,PT10M,PT1H,PT24M30S,PT2M,PT7M,..."
grep_workflow_log_ok grep-no-limit "\[1/nolimit/01:running\] health: execution timeout=None, polling intervals=3\*PT30S,PT10M,PT1H,..."

purge
