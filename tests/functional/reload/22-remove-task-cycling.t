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

#------------------------------------------------------------------------
# Test orphaned tasks do not stall the workflow after reload - GitHub #3306.

. "$(dirname "$0")/test_header"

set_test_number 3

# A workflow designed to orphan a single copy of a task 'bar' on self-reload,
# or stall and abort if the orphaned task triggers the #3306 bug.

init_workflow "${TEST_NAME_BASE}" <<__FLOW_CONFIG__
[scheduler]
   [[events]]
      inactivity timeout = PT25S
      abort on inactivity timeout = True
[scheduling]
   initial cycle point = 1
   final cycle point = 3
   cycling mode = integer
   runahead limit = P1
   [[dependencies]]
      [[[R/^/P1]]]
         graph = """foo[-P1] => foo
                    bar[-P1] => bar  # remove
                    bar:start => foo  # remove
                 """
[runtime]
   [[foo]]
      script = """
# Use poll function from test_header.
$(declare -f poll)
$(declare -f poll_grep)

# Remove bar and tell the server to reload.
if (( CYLC_TASK_CYCLE_POINT == CYLC_WORKFLOW_INITIAL_CYCLE_POINT )); then
   sed -i 's/^.*remove*$//g' "\${CYLC_WORKFLOW_RUN_DIR}/flow.cylc"
   cylc reload "\${CYLC_WORKFLOW_ID}"
   poll_grep -F 'Reload complete' "\${CYLC_WORKFLOW_RUN_DIR}/log/scheduler/log"
   # kill the long-running orphaned bar task.
   kill "\$(cat "\${CYLC_WORKFLOW_RUN_DIR}/work/1/bar/pid")"
fi
"""
   [[bar]]
      script = """
# Long sleep to ensure that bar does not finish before the reload.
# Store long sleep PID to enable kill after the reload.
sleep 1000 &
echo \$! > pid
wait"""
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --debug --no-detach "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-result"
cylc workflow-state "${WORKFLOW_NAME}" > workflow-state.log
contains_ok workflow-state.log << __END__
foo, 1, succeeded
bar, 1, succeeded
foo, 2, succeeded
foo, 3, succeeded
__END__

purge
