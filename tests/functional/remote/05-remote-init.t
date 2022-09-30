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
# Test remote initialisation - when remote init fails for an install target,
# check other platforms with same install target can be initialised.

export REQUIRE_PLATFORM='loc:remote fs:indep comms:tcp'
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
create_test_global_config "" "
[platforms]
    [[belle]]
        hosts = ${CYLC_TEST_HOST}
        install target = ${CYLC_TEST_INSTALL_TARGET}
        ssh command = garbage
    "

#-------------------------------------------------------------------------------
install_workflow

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

NAME='select-task-jobs.out'
DB_FILE="${WORKFLOW_RUN_DIR}/log/db"
sqlite3 "${DB_FILE}" \
    'SELECT name, submit_status, run_status, platform_name
     FROM task_jobs ORDER BY name' \
    >"${NAME}"
cmp_ok "${NAME}" <<__SELECT__
a|1||belle
b|1||belle
e|0|0|${CYLC_TEST_PLATFORM}
f|0|0|${CYLC_TEST_PLATFORM}
g|0|0|localhost
__SELECT__

grep_ok "ERROR - Incomplete tasks:" "${TEST_NAME_BASE}-run.stderr"
grep_ok "1/a did not complete required outputs" "${TEST_NAME_BASE}-run.stderr"
grep_ok "1/b did not complete required outputs" "${TEST_NAME_BASE}-run.stderr"

purge
exit
