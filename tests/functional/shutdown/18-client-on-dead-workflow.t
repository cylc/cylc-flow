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
# Test workflow shuts down with error on missing contact file
# And correct behaviour with client on the next 2 connection attempts.
. "$(dirname "$0")/test_header"
set_test_number 3
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on stall timeout = True
        stall timeout = PT0S
        abort on inactivity timeout = True
        inactivity timeout = PT3M
[scheduling]
    [[graph]]
        R1 = t1
[runtime]
    [[t1]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
cylc play --pause --no-detach "${WORKFLOW_NAME}" 1>'cylc-run.out' 2>&1 &
MYPID=$!
poll_workflow_running
kill "${MYPID}"  # Should leave behind the contact file
wait "${MYPID}" 1>'/dev/null' 2>&1 || true
run_fail "${TEST_NAME_BASE}-1" cylc ping "${WORKFLOW_NAME}"
contains_ok "${TEST_NAME_BASE}-1.stderr" <<__ERR__
WorkflowStopped: ${WORKFLOW_NAME} is not running
__ERR__
purge
exit
