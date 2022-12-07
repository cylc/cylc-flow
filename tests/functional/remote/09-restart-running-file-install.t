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
# Test restart remote init, file install and task messaging works for running tasks
# The test works as follows:
# - Starts workflow off with a remote starter task which will not complete
#   until restarted. It greps for updated file which will be remote installed on
#   restart.
# - On start of this starter task, update the file that is included in
#   remote file install for starter task.
# - Stop the workflow - this will leave starter task orphaned
# - Restart, starter task should remote install, authentication keys will be
#   updated which is verified by checking task messaging works (checks for
#   "(received)succeeded" in the logs).

export REQUIRE_PLATFORM='loc:remote comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 6

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    install = changing-file
    [[events]]
        abort on inactivity timeout = True
        inactivity timeout = PT1M
[scheduling]
    [[graph]]
        R1 = """
            starter:start => file-changer => stopper
        """
[runtime]
    [[starter]]
        platform = ${CYLC_TEST_PLATFORM}
        script = """
            while ! grep 'Restart Play' "${CYLC_WORKFLOW_RUN_DIR}/changing-file"; do
                sleep 1
            done
        """
    [[stopper]]
        script = cylc stop --now "${CYLC_WORKFLOW_ID}"
    [[file-changer]]
        script = echo Restart Play > ${CYLC_WORKFLOW_RUN_DIR}/changing-file
__FLOW_CONFIG__


echo "First Play" > "${WORKFLOW_RUN_DIR}/changing-file"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-start" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-restart" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"
LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"
grep_ok "remote file install complete" "${LOG}"
grep_ok "INFO - \[1/starter running job:01 flows:1\] (received)succeeded" "${LOG}"
ls "${WORKFLOW_RUN_DIR}/log/remote-install" > 'ls.out'
cmp_ok ls.out <<__RLOGS__
01-start-${CYLC_TEST_INSTALL_TARGET}.log
02-restart-${CYLC_TEST_INSTALL_TARGET}.log
__RLOGS__
purge
exit
