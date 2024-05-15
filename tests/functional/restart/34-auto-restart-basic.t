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
#-------------------------------------------------------------------------------
set_test_number 10
if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi
#-------------------------------------------------------------------------------
# run through the shutdown - restart procedure
BASE_GLOBAL_CONFIG="
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT2S
    [[events]]
        abort on inactivity timeout = True
        abort on stall timeout = True
        inactivity timeout = PT1M
        stall timeout = PT1M
[scheduler]
    [[run hosts]]
        available = localhost, ${CYLC_TEST_HOST}"

TEST_NAME="${TEST_NAME_BASE}"
init_workflow "${TEST_NAME}" - <<'__FLOW_CONFIG__'
[task parameters]
    foo = 1..25
[scheduling]
    [[graph]]
        R1 = "task<foo> => task<foo+1>"
[runtime]
    [[task<foo>]]
    [[task_26]]
__FLOW_CONFIG__

# run workflow on localhost normally
create_test_global_config '' "${BASE_GLOBAL_CONFIG}"
run_ok "${TEST_NAME}-workflow-start" \
    cylc play "${WORKFLOW_NAME}" --host=localhost -s 'FOO="foo"' -v
cylc workflow-state "${WORKFLOW_NAME}//1/task_foo01:succeeded" --interval=1 --max-polls=20 >& $ERR

# condemn localhost
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        condemned = $(hostname)
"
# test shutdown procedure - scan the first log file
FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME}-shutdown-log-scan" "${FILE}" 20 1 \
    'The Cylc workflow host will soon become un-available' \
    'Workflow shutting down - REQUEST(NOW-NOW)' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    "Workflow now running on \"${CYLC_TEST_HOST}\""
LATEST_TASK=$(cylc workflow-state --old-format "${WORKFLOW_NAME}//*/*:succeeded" \
    | cut -d ',' -f 1 | sort | tail -n 1 | sed 's/task_foo//')

# test restart procedure  - scan the second log file created on restart
poll_workflow_restart
FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME}-restart-log-scan" "${FILE}" 20 1 \
    "Scheduler: url=tcp://$(get_fqdn "${CYLC_TEST_HOST}")"
run_ok "${TEST_NAME}-restart-success" \
    cylc workflow-state "${WORKFLOW_NAME}//1/$(printf 'task_foo%02d' $(( LATEST_TASK + 3 ))):succeeded \
        --interval=1 --max-polls=60

# check the command the workflow has been restarted with
run_ok "${TEST_NAME}-contact" cylc get-contact "${WORKFLOW_NAME}"
grep_ok "cylc play ${WORKFLOW_NAME} -v --host=${CYLC_TEST_HOST} --host=localhost" \
    "${TEST_NAME}-contact.stdout"

# stop workflow
cylc stop "${WORKFLOW_NAME}" --kill --max-polls=10 --interval=2 2>'/dev/null'

# Check correct number of logs
ls "${WORKFLOW_RUN_DIR}/log/scheduler/" > ls_logs.out
cmp_ok ls_logs.out << __EOF__
01-start-01.log
02-restart-02.log
log
__EOF__

purge
