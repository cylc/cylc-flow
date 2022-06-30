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
# Test task event handler runs after "--abort-if-any-task-fails".
. "$(dirname "$0")/test_header"

set_test_number 5

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --no-detach --abort-if-any-task-fails "${WORKFLOW_NAME}"
LOGD="$RUN_DIR/${WORKFLOW_NAME}/log"
grep_ok "ERROR - Workflow shutting down - AUTOMATIC(ON-TASK-FAILURE)" \
    "${LOGD}/scheduler/log"
JLOGD="${LOGD}/job/1/t1/01"
# Check that 1/t1 event handler runs
run_ok "${TEST_NAME_BASE}-activity-log" \
    grep -q -F \
    "[(('event-handler-00', 'failed'), 1) out] Unfortunately 1/t1 failed" \
    "${JLOGD}/job-activity.log"
# Check that t2.1 did not run
exists_fail "${LOGD}/1/t2"
purge
exit
