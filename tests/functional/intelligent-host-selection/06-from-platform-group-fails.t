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
# Test that Cylc fails sensibly when a plaform group with no
# accessible hosts is selected.
# n.b. We don't care about definition order in this test becuase all
# hosts and platforms fail.
. "$(dirname "$0")/test_header"
set_test_number 12
#-------------------------------------------------------------------------------
# Create `global.cylc`` here rather than use
# `test_header.create_test_global_config`` method which appends
# to existing config: Stop users accidentally creating platforms which would
# match the Cylc 7 settings in `flow.cylc`.
cat >> 'global.cylc' <<__HERE__
[platforms]
    [[badhostplatform1]]
        hosts = bad_host1, bad_host2
    [[badhostplatform2]]
        hosts = bad_host3, bad_host4

[platform groups]
    [[badplatformgroup]]
        platforms = badhostplatform1, badhostplatform2
__HERE__

export CYLC_CONF_PATH="${PWD}"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

logfile="${WORKFLOW_RUN_DIR}/log/workflow/log"

# Check workflow fails for the reason we want it to fail
named_grep_ok \
    "Workflow stalled with 1/bad (submit-failed)" \
    "1/bad did not complete required outputs" \
    "$logfile"

# Look for message indicating that remote init has failed on each bad_host
# on every bad platform.
platform='badhostplatform1'
for host in {1..2}; do
    host="bad_host${host}"
    log_scan \
        "${TEST_NAME_BASE}-remote-init-fail-${host}" \
        "${logfile}" 1 0 \
        "platform: ${platform} - remote init (on ${host})" \
        "platform: ${platform} - Could not connect to ${host}."
done
platform='badhostplatform2'
for host in {3..4}; do
    host="bad_host${host}"
    log_scan \
        "${TEST_NAME_BASE}-remote-init-fail-${host}" \
        "${logfile}" 1 0 \
        "platform: ${platform} - remote init (on ${host})" \
        "platform: ${platform} - Could not connect to ${host}."
done

# Look for message indicating that remote init has failed.
named_grep_ok \
    "platform: badhostplatform. - initialisation did not complete (no hosts were reachable)" \
    "platform: badhostplatform. - initialisation did not complete (no hosts were reachable)" \
    "${logfile}"

purge
exit 0
