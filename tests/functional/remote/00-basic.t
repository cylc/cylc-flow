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
# Test remote host settings.
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
create_test_global_config "" "
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        retrieve job logs = True
"
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" basic
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-platform
sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    "SELECT platform_name FROM task_jobs WHERE name=='foo'" >'foo-host.txt'
cmp_ok 'foo-host.txt' <<<"${CYLC_TEST_PLATFORM}"
#-------------------------------------------------------------------------------
# Check that the remote job has actually been run on the correct remote by
# checking it's job.out file for @CYLC_TEST_HOST
REMOTE_HOST_FQDN="$(ssh "${CYLC_TEST_HOST}" hostname -f)"
TEST_NAME=${TEST_NAME_BASE}-ensure-remote-run
grep_ok \
    "^$REMOTE_HOST_FQDN" \
    "${WORKFLOW_RUN_DIR}/log/job/1/foo/NN/job.out"
#-------------------------------------------------------------------------------
purge
exit
