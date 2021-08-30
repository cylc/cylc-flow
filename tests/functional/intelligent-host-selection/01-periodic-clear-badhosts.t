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
# Test mainloop plugin periodically clears badhosts.
# By setting the interval to << small we can also test whether job log retrieval
# and remote tidy work.
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 6

# We don't use the usual ``create_test_global_config`` because we need to pin
# the result of ``get_random_platform_for_install_target(install_target)`` to
# mixedhostplatform.
cat >>'global.cylc' <<__HERE__
    # set a default timeout for all flow runs to avoid hanging tests
    [scheduler]
        [[events]]
            inactivity = PT5M
            stall timeout = PT5M
            abort on inactivity = true
            abort on stall timeout = true
        [[main loop]]
            [[[reset bad hosts]]]
                interval = PT1S
    [platforms]
        [[mixedhostplatform]]
            hosts = unreachable_host, ${CYLC_TEST_HOST}
            install target = ${CYLC_TEST_INSTALL_TARGET}
            retrieve job logs = True
            [[[selection]]]
                method = 'definition order'
__HERE__

export CYLC_CONF_PATH="${PWD}"

#-------------------------------------------------------------------------------

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

# Periodic clearance of badhosts happened:
named_grep_ok "periodic clearance message" \
    "Clearing bad hosts: {'unreachable_host'}" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"

# job log retrieval failed on the definition order attempt (us):
named_grep_ok "definition order job log retrieval fails" \
    "\"job-logs-retrieve\" failed because \"unreachable_host\" is not available right now" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"

# job-log retrival actually works:
ls "${WORKFLOW_RUN_DIR}/log/job/1/mixedhosttask/NN/" > "mixedhosttask.log.ls"
cmp_ok "mixedhosttask.log.ls" <<__HERE__
job
job-activity.log
job.err
job.out
job.status
job.xtrace
__HERE__

# remote tidy fails definition order time round"
named_grep_ok "definition order remote tidy fails" \
    "Tried to tidy remote platform: 'mixedhostplatform' using host 'unreachable_host' but failed; trying a different host" \
    "${WORKFLOW_RUN_DIR}/log/workflow/log"

purge "${WORKFLOW_NAME}" "mixedhostplatform"
exit 0
