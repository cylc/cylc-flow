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
# Test "cylc stop --now --now".
. "$(dirname "$0")/test_header"

set_test_number 9

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --no-detach "${WORKFLOW_NAME}"
LOGD="$RUN_DIR/${WORKFLOW_NAME}/log"
grep_ok 'INFO - Workflow shutting down - REQUEST(NOW-NOW)' "${LOGD}/scheduler/log"
grep_ok 'WARNING - Orphaned tasks' "${LOGD}/scheduler/log"
grep_ok '\* 1/t1 (running)' "${LOGD}/scheduler/log"
JLOGD="${LOGD}/job/1/t1/01"
# Check that 1/t1 event handler runs
run_fail "${TEST_NAME_BASE}-activity-log-succeeded" \
    grep -q -F \
    "[(('event-handler-00', 'succeeded'), 1) out] Well done 1/t1 succeeded" \
    "${JLOGD}/job-activity.log"
run_fail "${TEST_NAME_BASE}-activity-log-started" \
    grep -q -F \
    "[(('event-handler-00', 'started'), 1) out] Hello 1/t1 started" \
    "${JLOGD}/job-activity.log"
# Check that 1/t2 did not run
exists_fail "${LOGD}/job/1/t2"
# In SoD the restart does not stall and abort, because 1/t1:failed can be removed
# as handled.
workflow_run_ok "${TEST_NAME_BASE}-restart" cylc play --no-detach "${WORKFLOW_NAME}"
purge
exit
