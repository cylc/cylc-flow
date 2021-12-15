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
        'SELECT value FROM workflow_params WHERE key=="stopcp";' > stopcp.out
    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
        'SELECT cycle, name, status FROM task_pool ORDER BY cycle, name;' > taskpool.out
}

set_test_number 17
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# Check that the config stop point gets stored in DB
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --no-detach "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1970"'
dumpdbtables
cmp_ok stopcp.out <<< '1972'
# Note we have manually stopped before the stop point
cmp_ok taskpool.out << '__OUT__'
1971|hello|waiting
__OUT__

# Check that --stopcp=reload takes value from flow.cylc on restart
workflow_run_ok "${TEST_NAME_BASE}-restart-cli-stopcp-reload" \
    cylc play --no-detach --stopcp=reload "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1971"' -s 'STOPCP="1973"'
dumpdbtables
cmp_ok stopcp.out <<< '1973'
cmp_ok taskpool.out << '__OUT__'
1972|hello|waiting
__OUT__

# Check that the stop point stored in DB works on restart
workflow_run_ok "${TEST_NAME_BASE}-restart-db-stopcp" \
    cylc play --no-detach "${WORKFLOW_NAME}"
dumpdbtables
# Stop point should be removed from DB once reached
cmp_ok stopcp.out < /dev/null
# Task 1974/hello (after stop point) should be spawned but not submitted
cmp_ok taskpool.out <<'__OUT__'
1974|hello|waiting
__OUT__

# Check that the command line stop point gets stored in DB.
workflow_run_ok "${TEST_NAME_BASE}-restart-cli-stopcp" \
    cylc play --no-detach --stopcp=1975 "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1974"'
dumpdbtables
cmp_ok stopcp.out <<< '1975'
# Note we have manually stopped before the stop point
cmp_ok taskpool.out << '__OUT__'
1975|hello|waiting
__OUT__

# Check that workflow stops immediately if restarted past stopcp
workflow_run_ok "${TEST_NAME_BASE}-restart-final" \
    cylc play --no-detach --stopcp=reload "${WORKFLOW_NAME}"
# Note the config value remains as 1973 (not 1972) because Jinja2 variables persist over restart
grep_workflow_log_ok "${TEST_NAME_BASE}-log-grep" "Setting stop cycle point: 1973"
dumpdbtables
cmp_ok stopcp.out < /dev/null
cmp_ok taskpool.out << '__OUT__'
1975|hello|waiting
__OUT__

purge
