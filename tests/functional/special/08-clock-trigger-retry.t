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
# Old-style clock trigger should only go ahead if xtriggers are satisfied
# https://github.com/cylc/cylc-flow/issues/5217

. "$(dirname "$0")/test_header"
set_test_number 4

init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduling]
    initial cycle point = 2015
    final cycle point = PT1S
    [[special tasks]]
        clock-trigger = foo(PT1H)
    [[graph]]
        T00 = foo

[runtime]
    [[foo]]
        execution retry delays = PT5S # hopefully enough time to check task doesn't resubmit immediately
        script = ((CYLC_TASK_TRY_NUMBER > 1))
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "$WORKFLOW_NAME"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "$WORKFLOW_NAME"

log_scan "${TEST_NAME_BASE}-log-scan" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 2 1 \
    "\[20150101.*/foo .* job:01 .* retrying in PT5S" \
    "xtrigger satisfied: _cylc_retry_20150101"
# (if task resubmits immediately instead of waiting PT5S, xtrigger msg will not appear)

purge
