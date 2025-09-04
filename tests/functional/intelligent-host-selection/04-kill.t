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
# Test job kill will retry on a different host if there is a connection failure

export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'
. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 6

create_test_global_config "" "
[scheduler]
    [[main loop]]
        [[[reset bad hosts]]]
            # Set the auto clearance of badhosts to be << small time so that
            # kill will need to retry, despite 'unreachable_host' being
            # idetified as unreachable by job submission.
            interval = PT5S

[platforms]
    [[goodhostplatform]]
        $(cylc config -i "[platforms][$CYLC_TEST_PLATFORM]")

    [[goodhostplatform]]
        hosts = ${CYLC_TEST_HOST}

    [[mixedhostplatform]]
        $(cylc config -i "[platforms][$CYLC_TEST_PLATFORM]")

    [[mixedhostplatform]]
        # Use a fake background job runner to get around the
        # single host restriction.
        job runner = my_background
        hosts = unreachable_host, ${CYLC_TEST_HOST}
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

# job kill for mixedhosttask should have attempted on both hosts
grep_workflow_log_ok "${TEST_NAME_BASE}-kill-failed" \
    'jobs-kill for mixedhostplatform on unreachable_host'  # fail
grep_workflow_log_ok "${TEST_NAME_BASE}-kill-retried" \
    "jobs-kill for mixedhostplatform on $CYLC_TEST_HOST"   # retry

# both job kills should succeed
grep_workflow_log_ok "${TEST_NAME_BASE}-kill-succeeded-goodhosttask" \
    '1/goodhosttask/01.* job killed'
grep_workflow_log_ok "${TEST_NAME_BASE}-kill-succeeded-mixedhosttask" \
    '1/mixedhosttask/01.* job killed'

purge
exit 0
