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

# Test that we can re-trigger a task in sim mode

. "$(dirname "$0")/test_header"
set_test_number 5

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-start" \
    cylc play "${WORKFLOW_NAME}" --mode=simulation

SCHD_LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Wait for stall, then check for first task failure:
poll_grep_workflow_log 'stall timer starts'

grep_ok '\[1/fail_fail_fail/01:running\] => failed' "${SCHD_LOG}"

# Trigger task again, and check that it too failed:
cylc trigger "${WORKFLOW_NAME}//1/fail_fail_fail"

poll_grep_workflow_log -E \
    '1/fail_fail_fail/02.* did not complete required outputs'

grep_ok '\[1/fail_fail_fail/02:running\] => failed' "${SCHD_LOG}"

run_ok "stop" cylc stop --max-polls=10 --interval=1 "${WORKFLOW_NAME}"

purge
