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

# Test kill a running simulation job

. "$(dirname "$0")/test_header"

set_test_number 3
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# run workflow in background
cylc play --debug -m simulation "${WORKFLOW_NAME}" >/dev/null 2>&1

# wait for simulated job start
poll_grep_workflow_log "1/foo.* running" -E

# kill it
run_ok killer cylc kill "${WORKFLOW_NAME}//1/foo"

# wait for shut down
poll_grep_workflow_log "INFO - DONE"

# check the sim job was kiled
grep_workflow_log_ok killed "1/foo.* failed" -E

purge
