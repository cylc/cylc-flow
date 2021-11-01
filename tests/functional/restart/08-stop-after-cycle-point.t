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

set_test_number 13
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# Check that the config stop point gets stored in DB
workflow_run_ok "${TEST_NAME_BASE}-1-run-no-cli-opts" \
    cylc play --no-detach "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1970"'
dumpdbtables
cmp_ok stopcp.out <<< '1972'
# Note we have manually stopped before the stop point
cmp_ok taskpool.out << '__OUT__'
1971|hello|waiting
__OUT__

# Check that the config stop point works (even after restart)
workflow_run_ok "${TEST_NAME_BASE}-1-restart" \
    cylc play --no-detach "${WORKFLOW_NAME}"
dumpdbtables
# Task hello.1973 (after stop point) should be spawned but not submitted
cmp_ok taskpool.out <<'__OUT__'
1973|hello|waiting
__OUT__

delete_db

# Check that the command line stop point gets stored in DB.
workflow_run_ok "${TEST_NAME_BASE}-2-run-cli-stop" \
    cylc play --no-detach --stopcp=1971 "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1970"'
dumpdbtables
cmp_ok stopcp.out <<< '1971'
# Note we have manually stopped before the stop point
cmp_ok taskpool.out << '__OUT__'
1971|hello|waiting
__OUT__
# Check that the command line stop point works (even after restart)...
workflow_run_ok "${TEST_NAME_BASE}-2-restart" \
    cylc play --no-detach "${WORKFLOW_NAME}"
dumpdbtables
cmp_ok taskpool.out << '__OUT__'
1972|hello|waiting
__OUT__

# ... unless we reload stop point - takes value from final cycle point
# Note: we might want to rethink that - https://github.com/cylc/cylc-flow/issues/4062
workflow_run_ok "${TEST_NAME_BASE}-2-restart-cli-reload" \
    cylc play --no-detach --stopcp=reload "${WORKFLOW_NAME}" \
    -s 'MANUAL_SHUTDOWN="1973"'
dumpdbtables
cmp_ok stopcp.out <<< '1974'

purge
