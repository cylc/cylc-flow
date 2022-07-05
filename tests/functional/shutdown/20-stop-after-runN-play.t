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
# Test workflow shuts down, having been started with cylc play flow/runN 

. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
#-------------------------------------------------------------------------------

make_rnd_workflow
pushd "${RND_WORKFLOW_SOURCE}" || exit 1

cat > 'flow.cylc' <<__FLOW_CONFIG__
[scheduler]
    [[events]]
        abort on inactivity timeout = True
        inactivity timeout = PT3M
[scheduling]
    [[graph]]
        R1 = t1 
[runtime]
    [[t1]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-install" cylc install 2>'/dev/null'
popd || exit 1
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${RND_WORKFLOW_RUNDIR}/runN"
run_ok "${TEST_NAME_BASE}-play" cylc play "${RND_WORKFLOW_NAME}/runN" --pause
LOG="${RND_WORKFLOW_RUNDIR}/run1/log/scheduler/log"
run_ok "${TEST_NAME_BASE}-stop" cylc stop --now --now "${RND_WORKFLOW_NAME}/run1"
log_scan "${TEST_NAME_BASE}-log-stop" "${LOG}" 20 1 \
"INFO - Workflow shutting down - REQUEST(NOW-NOW)"
# stop workflow - workflow should already by stopped but just to be safe
cylc stop --max-polls=10 --interval=2 --kill "${RND_WORKFLOW_NAME}/runN" 2>'/dev/null'

purge_rnd_workflow
