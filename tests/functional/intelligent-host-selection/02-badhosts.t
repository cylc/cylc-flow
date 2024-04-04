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
# Test remote initialisation still fails where a task has a platform
# with only unreachable hosts.
# n.b. Hosts picked for unlikelyhood of names matching any real host.
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 6

# Uses a fake background job runner to get around the single host restriction.

create_test_global_config "" "
[platforms]
    [[badhostplatform]]
        job runner = my_background
        hosts = e9755ca30f5, 3c0b4799402
        install target = ${CYLC_TEST_INSTALL_TARGET}
        retrieve job logs = True
        [[[selection]]]
            method = definition order

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
# Uncomment to print config for manual testing of workflow.
# cylc config -i '[platforms]' >&2

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the fake background job runner.
cp -r "${TEST_SOURCE_DIR}/lib" "${WORKFLOW_RUN_DIR}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

LOGFILE="${WORKFLOW_RUN_DIR}/log/scheduler/log"

# Check that badhosttask has submit failed, but not good or mixed
named_grep_ok "badhost task submit failed" \
    "1/badhosttask.* submit-failed" "${LOGFILE}"
named_grep_ok "goodhost suceeded" \
    "1/mixedhosttask.* succeeded" "${LOGFILE}"
named_grep_ok "mixedhost task suceeded" \
    "1/goodhosttask.* succeeded" "${LOGFILE}"

# Check that when a task fail badhosts associated with that task's platform
# are removed from the badhosts set.
named_grep_ok "remove task platform bad hosts after submit-fail" \
    "initialisation did not complete (no hosts were reachable)" \
    "${LOGFILE}"

purge
exit 0
