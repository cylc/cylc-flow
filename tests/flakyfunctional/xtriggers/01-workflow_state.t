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

# Test workflow-state xtriggers with workflow depends on an upstream workflow
# that stops once cycle short, so it should abort with waiting tasks.

. "$(dirname "$0")/test_header"
set_test_number 8

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Register and validate the upstream workflow.
WORKFLOW_NAME_UPSTREAM="${WORKFLOW_NAME}-upstream"
cylc install "${TEST_DIR}/${WORKFLOW_NAME}/upstream" --workflow-name="${WORKFLOW_NAME_UPSTREAM}" --no-run-name
run_ok "${TEST_NAME_BASE}-validate-up" cylc validate --debug "${WORKFLOW_NAME_UPSTREAM}"

# Validate the downstream test workflow.
run_ok "${TEST_NAME_BASE}-validate" \
    cylc val --debug --set="UPSTREAM='${WORKFLOW_NAME_UPSTREAM}'" "${WORKFLOW_NAME}"

# Run the upstream workflow and detach (not a test).
cylc play "${WORKFLOW_NAME_UPSTREAM}"

# Run the test workflow - it should fail after inactivity ...
TEST_NAME="${TEST_NAME_BASE}-run-fail"
workflow_run_fail "${TEST_NAME}" \
   cylc play --set="UPSTREAM='${WORKFLOW_NAME_UPSTREAM}'" --no-detach "${WORKFLOW_NAME}"

WORKFLOW_LOG="$(cylc cat-log -m 'p' "${WORKFLOW_NAME}")"
grep_ok 'WARNING - inactivity timer timed out after PT20S' "${WORKFLOW_LOG}"

# ... with 2016/foo succeeded and 2016/FAM waiting.
cylc workflow-state --old-format "${WORKFLOW_NAME}//2016" >'workflow_state.out'
contains_ok 'workflow_state.out' << __END__
foo, 2016, succeeded
f3, 2016, waiting
f1, 2016, waiting
f2, 2016, waiting
__END__

# Check broadcast of xtrigger outputs to dependent tasks.
JOB_LOG="$(cylc cat-log -f 'j' -m 'p' "${WORKFLOW_NAME}//2015/f1")"
contains_ok "${JOB_LOG}" << __END__
    upstream_workflow_id="${WORKFLOW_NAME_UPSTREAM}"
    upstream_task_id="2015/foo"
    upstream_task_selector="data_ready"
    upstream_flow_number="1"
__END__

# Check broadcast of xtrigger outputs is recorded: 1) in the workflow log...
#
# Lines are those which should appear after a '<datetimestamp> INFO - Broadcast
# set' ('+') and later '... INFO - Broadcast cancelled:' ('-') line, where we
# use as a test case an arbitrary task where such setting & cancellation occurs:
contains_ok "${WORKFLOW_LOG}" << __LOG_BROADCASTS__
${LOG_INDENT}+ [2015/f1] [environment]upstream_workflow_id=${WORKFLOW_NAME_UPSTREAM}
${LOG_INDENT}+ [2015/f1] [environment]upstream_task_id=2015/foo
${LOG_INDENT}+ [2015/f1] [environment]upstream_task_selector=data_ready
${LOG_INDENT}+ [2015/f1] [environment]upstream_flow_number=1
${LOG_INDENT}- [2015/f1] [environment]upstream_workflow_id=${WORKFLOW_NAME_UPSTREAM}
${LOG_INDENT}- [2015/f1] [environment]upstream_task_id=2015/foo
${LOG_INDENT}- [2015/f1] [environment]upstream_task_selector=data_ready
${LOG_INDENT}- [2015/f1] [environment]upstream_flow_number=1
__LOG_BROADCASTS__
# ... and 2) in the DB.
TEST_NAME="${TEST_NAME_BASE}-check-broadcast-in-db"
if ! command -v 'sqlite3' >'/dev/null'; then
    skip 1 "sqlite3 not installed?"
fi
DB_FILE="${RUN_DIR}/${WORKFLOW_NAME}/log/db"
NAME='db-broadcast-states.out'
sqlite3 "${DB_FILE}" \
    'SELECT change, point, namespace, key, value FROM broadcast_events
     ORDER BY time, change, point, namespace, key' >"${NAME}"
contains_ok "${NAME}" << __DB_BROADCASTS__
+|2015|f1|[environment]upstream_workflow_id|${WORKFLOW_NAME_UPSTREAM}
+|2015|f1|[environment]upstream_task_id|2015/foo
+|2015|f1|[environment]upstream_task_selector|data_ready
+|2015|f1|[environment]upstream_flow_number|1
-|2015|f1|[environment]upstream_workflow_id|${WORKFLOW_NAME_UPSTREAM}
-|2015|f1|[environment]upstream_task_id|2015/foo
-|2015|f1|[environment]upstream_task_selector|data_ready
-|2015|f1|[environment]upstream_flow_number|1
__DB_BROADCASTS__

purge

# Clean up the upstream workflow, just in case (expect error here, but exit 0):
cylc stop --now "${WORKFLOW_NAME_UPSTREAM}" --max-polls=20 --interval=2 \
    >'/dev/null' 2>&1
purge "${WORKFLOW_NAME_UPSTREAM}"
