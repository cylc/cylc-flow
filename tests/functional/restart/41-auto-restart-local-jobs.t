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
export REQUIRE_PLATFORM='loc:remote fs:shared runner:background'
. "$(dirname "$0")/test_header"
# shellcheck disable=SC2153
export CYLC_TEST_HOST2="${CYLC_TEST_HOST}"
export CYLC_TEST_HOST1="${HOSTNAME}"
if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi
set_test_number 12
#-------------------------------------------------------------------------------
BASE_GLOBAL_CONFIG="
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT2S
    [[events]]
        abort on inactivity timeout = True
        abort on stall timeout = True
        inactivity timeout = PT2M
        stall timeout = PT2M
"

init_workflow "${TEST_NAME_BASE}" <<< '
[scheduling]
    [[graph]]
        R1 = foo => bar
[runtime]
    [[foo]]
        # we will trigger bar manually later
        script = sleep 15; false
    [[bar]]
        script = sleep 60
'
cd "${WORKFLOW_RUN_DIR}" || exit 1

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST1}
"

cylc play "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# auto stop-restart - normal mode:
#     ensure the workflow WAITS for local jobs to complete before restarting
TEST_NAME="${TEST_NAME_BASE}-normal-mode"

cylc workflow-state "${WORKFLOW_NAME}" --task='foo' --status='running' --point=1 \
    --interval=1 --max-polls=20 >& $ERR

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST1}, ${CYLC_TEST_HOST2}
        condemned = ${CYLC_TEST_HOST1}
"

LOG_FILE="$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)"
log_scan "${TEST_NAME}-stop" "${LOG_FILE}" 40 1 \
    'The Cylc workflow host will soon become un-available' \
    'Waiting for jobs running on localhost to complete' \
    'Waiting for jobs running on localhost to complete' \
    'Workflow shutting down - REQUEST(NOW-NOW)' \
    "Attempting to restart on \"${CYLC_TEST_HOST2}\""
# we shouldn't have any orphaned tasks because we should
# have waited for them to complete
grep_fail 'orphaned task' "$LOG_FILE"

poll_workflow_restart
named_grep_ok "restart-log-grep" "Workflow now running on \"${CYLC_TEST_HOST2}\"" "$LOG_FILE"
#-------------------------------------------------------------------------------
# auto stop-restart - force mode:
#     ensure the workflow DOESN'T WAIT for local jobs to complete before stopping
TEST_NAME="${TEST_NAME_BASE}-force-mode"

cylc trigger "${WORKFLOW_NAME}//1/bar"
cylc workflow-state "${WORKFLOW_NAME}" --task='bar' --status='running' --point=1 \
    --interval=1 --max-polls=20 >& $ERR

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST1}, ${CYLC_TEST_HOST2}
        condemned = ${CYLC_TEST_HOST2}!
"

LOG_FILE="$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)"
log_scan "${TEST_NAME}-stop" "${LOG_FILE}" 40 1 \
    'The Cylc workflow host will soon become un-available' \
    'This workflow will be shutdown as the workflow host is unable to continue' \
    'Workflow shutting down - REQUEST(NOW)' \
    'Orphaned task jobs:' \
    '* 1/bar (running)'

cylc stop "${WORKFLOW_NAME}" --now --now 2>/dev/null || true
poll_workflow_stopped
sleep 1
purge
exit
