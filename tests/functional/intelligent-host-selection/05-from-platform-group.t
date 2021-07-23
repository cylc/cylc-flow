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
set_test_number 7

create_test_global_config "" "
[platforms]
    [[mixedhostplatform]]
        hosts = unreachable_host, ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        [[[selection]]]
            method = 'definition order'
    [[badhostplatform]]
        hosts = bad_host1, bad_host2
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True

[platform groups]
    [[mixedplatformgroup]]
        platforms = badhostplatform, mixedhostplatform
        [[[selection]]]
            method = definition order
    [[goodplatformgroup]]
        platforms = mixedhostplatform
        [[[selection]]]
            method = definition order
    "
#-------------------------------------------------------------------------------

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# Task where platform = mixedplatformgroup fails totally on badhostplatform,
# fails on the first host of mixedhostplatform, then, finally suceeds.
named_grep_ok "job submit fails for bad_host1" "\"jobs-submit\" failed.*\"bad_host1\"" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"
named_grep_ok "job submit fails for bad_host2" "\"jobs-submit\" failed.*\"bad_host2\"" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"
named_grep_ok "job submit fails for badhostplatform" "badhostplatform: Tried all the hosts" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"
named_grep_ok "job submit fails for unreachable_host" "\"jobs-submit\" failed.*\"bad_host1\"" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"
named_grep_ok "job submit _finally_ works" "[ugly.1].*preparing => submitted" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"

purge
exit 0
