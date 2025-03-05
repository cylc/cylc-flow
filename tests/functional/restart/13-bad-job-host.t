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
# Test restarting a workflow when the host of a submitted or running job is not
# available. https://github.com/cylc/cylc-flow/issues/1327
export REQUIRE_PLATFORM='loc:remote comms:tcp'
. "$(dirname "$0")/test_header"
set_test_number 4
install_workflow "${TEST_NAME_BASE}" bad-job-host
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug --no-detach --abort-if-any-task-fails "${WORKFLOW_NAME}"
# Modify DB with garbage host
CYLC_WORKFLOW_RUN_DIR="$RUN_DIR/${WORKFLOW_NAME}"
for DB_NAME in 'log/db' '.service/db'; do
    sqlite3 "${CYLC_WORKFLOW_RUN_DIR}/${DB_NAME}" \
        "UPDATE task_jobs SET platform_name='garbage' WHERE name=='t-remote';"
done
workflow_run_fail "${TEST_NAME_BASE}-restart" cylc play --debug --no-detach --abort-if-any-task-fails "${WORKFLOW_NAME}"
grep_ok PlatformLookupError "${CYLC_WORKFLOW_RUN_DIR}/log/scheduler/log"
#-------------------------------------------------------------------------------
purge
exit
