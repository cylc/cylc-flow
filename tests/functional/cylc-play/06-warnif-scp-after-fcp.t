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

# test that cylc play warns if FCP before Stop Point.

. "$(dirname "$0")/test_header"

set_test_number 7

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
    [[events]]
      # The third subtest will restart with an empty task pool.
      # This ensures the workflow shuts down prompty.
      restart timeout = PT0S
[scheduling]
    initial cycle point = 1
    final cycle point = 2
    cycling mode = integer
    [[graph]]
        P1 = foo
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

for SCP in 1 2 3; do
    TEST_NAME="${TEST_NAME_BASE}-play-integer-scp=${SCP}"
        workflow_run_ok "${TEST_NAME}" cylc play "${WORKFLOW_NAME}" \
        --no-detach --stopcp="${SCP}"

    if [[ "${SCP}" -lt 3 ]]; then
        grep_ok "stop cycle point '.*'.*after.*final cycle point '.*'" \
            "${RUN_DIR}/${WORKFLOW_NAME}/log/scheduler/log" "-v"
    else
        grep_ok "stop cycle point '.*'.*after.*final cycle point '.*'" \
            "${RUN_DIR}/${WORKFLOW_NAME}/log/scheduler/log"
    fi
done

purge
