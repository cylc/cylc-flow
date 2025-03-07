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
# Test re-run event handler on restart.
. "$(dirname "$0")/test_header"
set_test_number 7
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

WORKFLOWD="$RUN_DIR/${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}" --debug --no-detach
sqlite3 "${WORKFLOWD}/log/db" \
    "SELECT COUNT(*) FROM task_action_timers WHERE ctx_key GLOB '*event-handler-00*'" \
    >"${TEST_NAME_BASE}-db-n-entries"
cmp_ok "${TEST_NAME_BASE}-db-n-entries" <<<'1'
workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play "${WORKFLOW_NAME}" --debug --no-detach
cmp_ok "${WORKFLOWD}/file" <<'__TEXT__'
1
2
__TEXT__
grep_ok 'LOADING task action timers' "${WORKFLOWD}/log/scheduler/log"
grep_ok "+ 1/t01 \[\['event-handler-00', 'succeeded'\], 1\]" "${WORKFLOWD}/log/scheduler/log"

purge
exit
