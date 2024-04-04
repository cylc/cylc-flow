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
# Test that Cylc Can select a host from a platform group
# Failing if there is no good host _any_ platform
# Succeeding if there is no bad host on any platform in the group
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 11

# Uses a fake background job runner to get around the single host restriction.

create_test_global_config "" "
[platforms]
    [[${CYLC_TEST_PLATFORM}]]
        # mixed host platform
        job runner = my_background
        hosts = unreachable_host, ${CYLC_TEST_HOST}
        [[[selection]]]
            method = 'definition order'
    [[badhostplatform]]
        job runner = my_background
        hosts = bad_host1, bad_host2
        [[[selection]]]
            method = 'definition order'

[platform groups]
    [[mixedplatformgroup]]
        platforms = badhostplatform, ${CYLC_TEST_PLATFORM}
        [[[selection]]]
            method = definition order
    [[goodplatformgroup]]
        platforms = ${CYLC_TEST_PLATFORM}
        [[[selection]]]
            method = definition order
"
#-------------------------------------------------------------------------------
# Uncomment to print config for manual testing of workflow.
# cylc config -i '[platforms]' >&2
# cylc config -i '[platform groups]' >&2

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the fake background job runner.
cp -r "${TEST_SOURCE_DIR}/lib" "${WORKFLOW_RUN_DIR}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}" --reference-test

# should try remote-init on bad_host{1,2} then fail
log_scan \
    "${TEST_NAME_BASE}-badhostplatformgroup" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    'platform: badhostplatform - remote init (on bad_host1)' \
    'platform: badhostplatform - Could not connect to bad_host1.' \
    'platform: badhostplatform - remote init (on bad_host2)' \
    'platform: badhostplatform - Could not connect to bad_host2.' \

# should try remote-init on unreachable_host, then $CYLC_TEST_HOST then pass
log_scan \
    "${TEST_NAME_BASE}-goodplatformgroup" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log" 1 0 \
    "platform: ${CYLC_TEST_PLATFORM} - remote init (on unreachable_host)" \
    "platform: ${CYLC_TEST_PLATFORM} - Could not connect to unreachable_host." \
    "platform: ${CYLC_TEST_PLATFORM} - remote init (on ${CYLC_TEST_HOST})" \
    "platform: ${CYLC_TEST_PLATFORM} - remote file install (on ${CYLC_TEST_HOST})" \
    "\[1/ugly/01:preparing\] => submitted"

purge
exit 0
