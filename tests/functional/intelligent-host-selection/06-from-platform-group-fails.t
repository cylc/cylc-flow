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
export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'

. "$(dirname "$0")/test_header"

#-------------------------------------------------------------------------------
set_test_number 9

create_test_global_config "" "
[platforms]
    [[badhostplatform1]]
        hosts = bad_host1, bad_host2
        install target = ${CYLC_TEST_INSTALL_TARGET}
    [[badhostplatform2]]
        hosts = bad_host3, bad_host4
        install target = ${CYLC_TEST_INSTALL_TARGET}

[platform groups]
    [[badplatformgroup]]
        platforms = badhostplatform1, badhostplatform2
    "
#-------------------------------------------------------------------------------
# Uncomment to print config for manual testing of workflow.
# cylc config -i '[platforms]' >&2
# cylc config -i '[platform groups]' >&2

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

logfile="${WORKFLOW_RUN_DIR}/log/workflow/log"

# Check workflow fails for the reason we want it to fail
named_grep_ok "Workflow stalled with bad.1 (submit-failed)"\
    "bad.1 (submit-failed)" "$logfile"

# Look for message indicating that remote init has failed on each bad_host
# on every bad platform.
for host in {1..4}; do
    named_grep_ok "job submit fails for bad_host${host}"\
        "\"remote-init\" failed.*\"bad_host${host}\"" \
        "$logfile"
done

# Look for message indicating that remote init has failed on both bad platforms
# in the platform group.
for platform in {1..2}; do
    named_grep_ok "job submit fails for badplatform${platform}"\
    "badhostplatform${platform}: Tried all the hosts"\
    "$logfile"
done

# purge
exit 0
