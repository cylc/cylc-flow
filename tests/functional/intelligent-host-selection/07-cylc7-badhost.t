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
#------------------------------------------------------------------------------
# Test task does not run on localhost if Cylc 7 syntax
# [runtime][<task>][remote]host is unreachable -
# https://github.com/cylc/cylc-flow/issues/4569

. "$(dirname "$0")/test_header"
set_test_number 4

# Host name picked for unlikelihood of matching any real host
BAD_HOST="f65b965bb914"

create_test_global_config "" "
[platforms]
    [[badhostplatform]]
        hosts = ${BAD_HOST}
"

init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduler]
    [[events]]
        stall timeout = PT0M
        abort on stall timeout = True
[scheduling]
    cycling mode = integer
    [[graph]]
        R1 = sattler
[runtime]
    [[sattler]]
        [[[remote]]]
            host = ${BAD_HOST}
__FLOW__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --no-detach "${WORKFLOW_NAME}"

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-1" \
    "platform: badhostplatform - initialisation did not complete"

grep_workflow_log_ok "${TEST_NAME_BASE}-grep-2" "CRITICAL - Workflow stalled"

purge
