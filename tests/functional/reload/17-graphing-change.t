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
# Test that removing a task from the graph works OK.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 12

# shellcheck disable=SC2317
grep_workflow_log_n_times() {
    TEXT="$1"
    N_TIMES="$2"
    [[ $(grep -c "$TEXT" "${WORKFLOW_RUN_DIR}/log/scheduler/log") == "$N_TIMES" ]]
}
#-------------------------------------------------------------------------------
# test reporting of added tasks

# install workflow
install_workflow "${TEST_NAME_BASE}" 'graphing-change'
LOG_FILE="${WORKFLOW_RUN_DIR}/log/scheduler/log"

# start workflow in paused mode
run_ok "${TEST_NAME_BASE}-add-run" cylc play --debug --pause "${WORKFLOW_NAME}"

# change the flow.cylc file
cp "${TEST_SOURCE_DIR}/graphing-change/flow-1.cylc" \
    "${RUN_DIR}/${WORKFLOW_NAME}/flow.cylc"

# reload workflow
run_ok "${TEST_NAME_BASE}-add-reload" cylc reload "${WORKFLOW_NAME}"
poll grep_workflow_log_n_times 'Reload completed' 1

# check workflow log
grep_ok "Added task: 'one'" "${LOG_FILE}"
#-------------------------------------------------------------------------------
# test reporting or removed tasks

# change the flow.cylc file
cp "${TEST_SOURCE_DIR}/graphing-change/flow.cylc" \
    "${RUN_DIR}/${WORKFLOW_NAME}/flow.cylc"

# reload workflow
run_ok "${TEST_NAME_BASE}-remove-reload" cylc reload "${WORKFLOW_NAME}"
poll grep_workflow_log_n_times 'Reload completed' 2

# check workflow log
grep_ok "Removed task: 'one'" "${LOG_FILE}"
#-------------------------------------------------------------------------------
# test reporting of adding / removing / swapping tasks

# change the flow.cylc file
cp "${TEST_SOURCE_DIR}/graphing-change/flow-2.cylc" \
    "${RUN_DIR}/${WORKFLOW_NAME}/flow.cylc"

# Spawn a couple of task proxies, to get "task definition removed" message.
cylc set "${WORKFLOW_NAME}//1/foo"
cylc set "${WORKFLOW_NAME}//1/baz"
# reload workflow
run_ok "${TEST_NAME_BASE}-swap-reload" cylc reload "${WORKFLOW_NAME}"
poll grep_workflow_log_n_times 'Reload completed' 3

# check workflow log
grep_ok "Added task: 'one'" "${LOG_FILE}"
grep_ok "Added task: 'add'" "${LOG_FILE}"
grep_ok "Added task: 'boo'" "${LOG_FILE}"
grep_ok "\\[1/bar.*\\].*task definition removed" "${LOG_FILE}"
grep_ok "\\[1/bol.*\\].*task definition removed" "${LOG_FILE}"

run_ok "${TEST_NAME_BASE}-stop" \
    cylc stop --max-polls=10 --interval=2 "${WORKFLOW_NAME}"

purge
exit
