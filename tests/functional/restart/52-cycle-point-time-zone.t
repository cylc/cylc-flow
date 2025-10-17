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
# followed by a restart. Important for restarting a workflow after a system
# time zone change.

. "$(dirname "$0")/test_header"

set_test_number 6

init_workflow "${TEST_NAME_BASE}" << '__FLOW__'
#!jinja2
[scheduler]
    cycle point time zone = {{ CPTZ }}
    UTC mode = False
    allow implicit tasks = True
[scheduling]
    initial cycle point = now
    [[graph]]
        R1 = foo
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}" -s "CPTZ='Z'"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --pause -s "CPTZ='+0100'"
poll_workflow_running
cylc stop "${WORKFLOW_NAME}"
poll_workflow_stopped

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    "SELECT * FROM workflow_params WHERE key=='cycle_point_tz';" > 'dump.out'
cmp_ok 'dump.out' <<< 'cycle_point_tz|+0100'

# Simulate DST change
export TZ=UTC

workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play "${WORKFLOW_NAME}" --pause
poll_workflow_running

cylc stop "${WORKFLOW_NAME}"

log_scan "${TEST_NAME_BASE}-log-scan" "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    'LOADING saved workflow parameters' \
    '+ cycle point time zone = +0100'

purge
