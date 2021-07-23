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
# Test job polling. Set the auto clearance of badhosts to be << small time
# so that polling will need to retry.
export REQUIRE_PLATFORM='loc:remote fs:indep'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 4

create_test_global_config "" "
[scheduler]
    [[main loop]]
        [[[reset bad hosts]]]
            interval = PT1S

[platforms]
    [[goodhostplatform]]
        hosts = ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        communication method = poll
        execution polling intervals = PT0S, PT14M
        submission polling intervals = PT0S, PT41M

    [[mixedhostplatform]]
        hosts = unreachable_host, ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        communication method = poll
        execution polling intervals = PT0S, PT14M
        submission polling intervals = PT0S, PT41M
        [[[selection]]]
            method = 'definition order'
    "
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach \
    "${WORKFLOW_NAME}"

LOGFILE="${WORKFLOW_RUN_DIR}/log/workflow/log"

# Check that when a task fail badhosts associated with that task's platform
# are removed from the badhosts set.
named_grep_ok "job poll fails" \
    "\"jobs-poll\" failed because \"unreachable_host\" is not available right now." \
    "${LOGFILE}" "-P"

named_grep_ok "job poll retries & succeeds" \
    "\[jobs-poll out\] \[TASK JOB SUMMARY\].*1/mixedhosttask/01" \
    "${LOGFILE}"

purge
exit 0
