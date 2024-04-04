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

# Test custom severity event handling.
. "$(dirname "$0")/test_header"
set_test_number 6
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test "${WORKFLOW_NAME}"
FOO_ACTIVITY_LOG="${WORKFLOW_RUN_DIR}/log/job/1/foo/NN/job-activity.log"
WORKFLOW_LOG="${WORKFLOW_RUN_DIR}/log/scheduler/log"
grep_ok \
"\[(('event-handler-00', 'custom-1'), 1) out\] !!CUSTOM!! 1/foo fugu Data ready for barring" \
    "${FOO_ACTIVITY_LOG}"
grep_ok "1/foo.*Data ready for barring" "${WORKFLOW_LOG}" -E
grep_ok "1/foo.*Data ready for bazzing" "${WORKFLOW_LOG}" -E
grep_ok "1/foo.*Aren't the hydrangeas nice" "${WORKFLOW_LOG}" -E
purge
