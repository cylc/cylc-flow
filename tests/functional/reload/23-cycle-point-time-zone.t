#!/bin/bash
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
# Test saving and loading of cycle point time zone to/from database on a run
# followed by a reload. Important for reloading a workflow after a system
# time zone change.

. "$(dirname "$0")/test_header"

set_test_number 5

init_workflow "${TEST_NAME_BASE}" << '__FLOW__'
[scheduler]
    cycle point time zone = +0100
    allow implicit tasks = True
[scheduling]
    initial cycle point = now
    [[graph]]
        R1 = foo
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# Set time zone to +01:00
export TZ=BST-1

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --pause
poll_grep_workflow_log "Paused on start up"

# Simulate DST change
export TZ=UTC

run_ok "${TEST_NAME_BASE}-reload" cylc reload "${WORKFLOW_NAME}"
poll_grep_workflow_log "Reload completed"

cylc stop --now --now "${WORKFLOW_NAME}"

log_scan "${TEST_NAME_BASE}-log-scan" "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    'LOADING workflow parameters' \
    '+ cycle point time zone = +0100'

purge
