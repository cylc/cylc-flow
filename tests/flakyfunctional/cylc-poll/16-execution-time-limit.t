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

# Test execution time limit polling.
export REQUIRE_PLATFORM='loc:* comms:poll runner:background'
. "$(dirname "$0")/test_header"

set_test_number 5
create_test_global_config '' "
[platforms]
   [[$CYLC_TEST_PLATFORM]]
        submission polling intervals = PT2S
        execution polling intervals = PT1M
        execution time limit polling intervals = PT5S
"
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test -v --no-detach "${WORKFLOW_NAME}" --timestamp

LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"

log_scan "${TEST_NAME_BASE}-log" "${LOG}" 1 0 \
    "\[1/foo/01:submitted\] => running" \
    "\[1/foo/01:running\] poll now, (next in PT5S" \
    "\[1/foo/01:running\] (polled)failed/XCPU"

purge
