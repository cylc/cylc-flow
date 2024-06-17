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
# Test reload triggers a fresh file install

export REQUIRE_PLATFORM='loc:remote fs:indep comms:?(tcp|ssh)'
. "$(dirname "$0")/test_header"
set_test_number 4
create_test_global_config "" "
[platforms]
   [[${CYLC_TEST_PLATFORM}]]
       retrieve job logs = True
"
TEST_NAME="${TEST_NAME_BASE}"
install_workflow "${TEST_NAME}" "${TEST_NAME_BASE}"
echo "hello" > "${WORKFLOW_RUN_DIR}/changing-file"


run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"
# If new remote file install has completed task c job.out should have goodbye in it
grep_ok "goodbye" "${WORKFLOW_RUN_DIR}/log/job/1/c/01/job.out"


find "${WORKFLOW_RUN_DIR}/log/remote-install" -type f -name "*log" | wc -l >'find-remote-install-log'
cmp_ok 'find-remote-install-log' <<< '2'

purge
exit
