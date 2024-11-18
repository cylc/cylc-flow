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

# High-level test of `cylc remove --flow` option.
# Integration tests exist for more comprehensive coverage.

. "$(dirname "$0")/test_header"
set_test_number 6

init_workflow "${TEST_NAME_BASE}" <<'__EOF__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = foo
__EOF__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --pause

run_ok "${TEST_NAME_BASE}-remove" cylc remove "${WORKFLOW_NAME}//1/foo" --flow 1 --flow 2

cylc stop "${WORKFLOW_NAME}"
poll_workflow_stopped

grep_workflow_log_ok "${TEST_NAME_BASE}-grep" "Removed task(s): 1/foo (flows=1)"

# Simple additional test of DB:
TEST_NAME="${TEST_NAME_BASE}-workflow-state"
run_ok "$TEST_NAME" cylc workflow-state "$WORKFLOW_NAME"
cmp_ok "${TEST_NAME}.stdout" <<__EOF__
1/foo:waiting(flows=none)
__EOF__

purge
