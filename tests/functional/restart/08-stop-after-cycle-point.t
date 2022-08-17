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
# Check that workflow does not run beyond stopcp whether set in flow.cylc or
# on the command line.

. "$(dirname "$0")/test_header"

dumpdbtables() {
    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
        'SELECT value FROM workflow_params WHERE key=="stopcp";' > db_stopcp.out
    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' > db_taskpool.out.out
}

set_test_number 29
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Set the config stop point (accessed via Jinja2)
export CFG_STOPCP
CFG_STOPCP="1970"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"


# Check config stop point works
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --no-detach "${WORKFLOW_NAME}"
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1970"
dumpdbtables
# Task 1971/hello (after stop point) should be spawned but not submitted
cmp_ok db_taskpool.out.out << '__OUT__'
1971|hello|waiting
__OUT__
# Check that the config stop point does not get stored in DB
cmp_ok db_stopcp.out < /dev/null


CFG_STOPCP="1972"

# Check that changing config stop point has worked
workflow_run_ok "${TEST_NAME_BASE}-restart" \
    cylc play --no-detach "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1971"'
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1972"
dumpdbtables
# Note we have manually stopped at 1971 before the stop point at 1972:
#   1972: waiting
#   1973: waiting and runahead limited
cmp_ok db_taskpool.out.out << '__OUT__'
1972|hello|waiting
1973|hello|waiting
__OUT__
cmp_ok db_stopcp.out < /dev/null


# Check that the command line stop point works
workflow_run_ok "${TEST_NAME_BASE}-restart-cli-stopcp" \
    cylc play --no-detach --stopcp=1974 "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1973"'
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1974"
dumpdbtables
# Note we have manually stopped before the stop point
cmp_ok db_taskpool.out.out << '__OUT__'
1974|hello|waiting
1975|hello|waiting
__OUT__
# Check CLI stop point is stored in DB
cmp_ok db_stopcp.out <<< '1974'


# Check that the stop point stored in DB works on restart
workflow_run_ok "${TEST_NAME_BASE}-restart-db-stopcp" \
    cylc play --no-detach "${WORKFLOW_NAME}"
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1974"
dumpdbtables
cmp_ok db_taskpool.out.out <<'__OUT__'
1975|hello|waiting
__OUT__
# Stop point should be removed from DB once reached
cmp_ok db_stopcp.out < /dev/null


# Restart again with new CLI stop point
workflow_run_ok "${TEST_NAME_BASE}-restart-cli-stopcp-2" \
    cylc play --no-detach --stopcp=1978 "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1975"'
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1978"
dumpdbtables
# Note we have manually stopped before the stop point
cmp_ok db_taskpool.out.out << '__OUT__'
1976|hello|waiting
1977|hello|waiting
__OUT__
cmp_ok db_stopcp.out <<< '1978'


CFG_STOPCP="1979"

# Check that --stopcp=reload takes value from flow.cylc on restart
workflow_run_ok "${TEST_NAME_BASE}-restart-cli-stopcp-reload" \
    cylc play --no-detach --stopcp=reload "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1976"'
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1979"
dumpdbtables
cmp_ok db_taskpool.out.out << '__OUT__'
1977|hello|waiting
1978|hello|waiting
__OUT__
# Stop point should be removed from DB if --stopcp=reload used
cmp_ok db_stopcp.out < /dev/null


CFG_STOPCP="1971"

# Check that workflow stops immediately if restarted past stopcp
workflow_run_ok "${TEST_NAME_BASE}-restart-past-stopcp" \
    cylc play --no-detach "${WORKFLOW_NAME}"
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Stop point: 1971"
dumpdbtables
cmp_ok db_taskpool.out.out << '__OUT__'
1977|hello|waiting
1978|hello|waiting
__OUT__
cmp_ok db_stopcp.out < /dev/null

purge
