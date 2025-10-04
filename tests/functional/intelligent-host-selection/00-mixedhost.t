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
# Test remote initialisation - where a task has a platform with an unreachable
# host.
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 4

# Uses a fake background job runner to get around the single host restriction.

create_test_global_config "" "
[platforms]
    [[goodhostplatform]]
        hosts = ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True

    [[mixedhostplatform]]
        job runner = my_background
        hosts = unreachable_host, ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        [[[selection]]]
            method = 'definition order'
    "
#-------------------------------------------------------------------------------

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the fake background job runner.
cp -r "${TEST_SOURCE_DIR}/lib" "${WORKFLOW_RUN_DIR}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# Run a bunch of tests on the workflow logs to ensure that warning messages
# produced by Intelligent Host Selection Logic have happened.

named_grep_ok "${TEST_NAME_BASE}-unreachable-host-warning" \
    'unreachable_host has been added to the list of unreachable hosts' \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Ensure that retrying in this context doesn't increment try number:
grep_fail "1/mixedhosttask/02" "${WORKFLOW_RUN_DIR}/log/scheduler/log"

purge
exit 0
