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
# Test log dev-mode.

. "$(dirname "$0")/test_header"
set_test_number 5
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    final cycle point = 1
    [[graph]]
        P1 = t1
[runtime]
    [[t1]]
        script = true
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate-plain" \
    cylc validate "${WORKFLOW_NAME}"

run_ok "${TEST_NAME_BASE}-validate-vvv" \
    cylc validate --timestamp -vvv "${WORKFLOW_NAME}"
grep_ok " DEBUG - \[config:.*\]" "${TEST_NAME_BASE}-validate-vvv.stderr"


run_ok "${TEST_NAME_BASE}-validate-vvv--no-timestamp" \
    cylc validate -vvv "${WORKFLOW_NAME}"
grep_ok "^DEBUG - \[config:.*\]" "${TEST_NAME_BASE}-validate-vvv--no-timestamp.stderr"

purge
exit
