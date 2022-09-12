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
# ----------------------------------------------------------------------------
# Test that validation errors on play are logged before daemonisation

. "$(dirname "$0")/test_header"
set_test_number 3

init_workflow "${TEST_NAME_BASE}" <<'__FLOW__'
[scheduler]
    horse = dorothy
__FLOW__

run_fail "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_fail "$TEST_NAME" cylc play "${WORKFLOW_NAME}"

grep_ok "IllegalItemError: [scheduler]horse" "${TEST_NAME}.stderr" -F

purge
