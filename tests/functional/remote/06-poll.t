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
export REQUIRE_PLATFORM='loc:remote comms:poll'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
create_test_global_config "" "
[platforms]
    [[$CYLC_TEST_PLATFORM]]
        retrieve job logs = True
"
#-------------------------------------------------------------------------------
init_workflow "${TEST_NAME_BASE}" <<__HERE__
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = cylc message -- foo
        platform = $CYLC_TEST_PLATFORM
        [[[outputs]]]
            foo = foo
__HERE__
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play "${WORKFLOW_NAME}" \
    --debug \
    --no-detach

log_scan \
    "${TEST_NAME_BASE}-poll" \
    "$(cylc cat-log -m p "$WORKFLOW_NAME")" \
    10 \
    1 \
    '\[1/foo.* (polled)foo' \
    '\[1/foo.* (polled)succeeded'

purge
exit
