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
# Test intelligent host selection for job polling.
#
# Set the peridic clearance of unreachable hosts by
# `[scheduler][main loop][reset bad hosts]interval = PT1S` so that between
# Submission of a job and execution polling the list of bad hosts will have
# cleared. Having cleared bad hosts we can then test that polling goes through
# the host selection process.

export REQUIRE_PLATFORM='loc:remote fs:indep'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 4

# Uses a fake background job runner to get around the single host restriction.

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
        execution polling intervals = 10*PT3S
        submission polling intervals = PT0S, 5*PT2S

    [[mixedhostplatform]]
        job runner = my_background
        hosts = unreachable_host, ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        communication method = poll
        execution polling intervals = 10*PT3S
        submission polling intervals = PT0S, 5*PT2S
        [[[selection]]]
            method = 'definition order'
    "
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the fake background job runner.
cp -r "${TEST_SOURCE_DIR}/lib" "${WORKFLOW_RUN_DIR}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach \
    "${WORKFLOW_NAME}"

LOGFILE="${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Check that when a task fail badhosts associated with that task's platform
# are removed from the badhosts set.
named_grep_ok \
    "${TEST_NAME_BASE}-job-poll-fails" \
    "unreachable_host has been added to the list of unreachable hosts" \
    "${LOGFILE}"

named_grep_ok \
    "${TEST_NAME_BASE}-job-poll-retries-and-succeeds" \
    "\[jobs-poll out\] \[TASK JOB SUMMARY\].*1/mixedhosttask/01" \
    "${LOGFILE}"

purge
exit 0
