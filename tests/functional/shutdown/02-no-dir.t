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
# Test workflow can shutdown successfully if its run dir is deleted
. "$(dirname "$0")/test_header"
set_test_number 4

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

create_test_global_config "" "
[scheduler]
    [[main loop]]
        [[[health check]]]
            interval = PT10S"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
# Workflow run directory is now a symbolic link, so we can easily delete it.
SYM_WORKFLOW_RUND="${WORKFLOW_RUN_DIR}-sym"
SYM_WORKFLOW_NAME="${WORKFLOW_NAME}-sym"
ln -s "$(basename "${WORKFLOW_NAME}")" "${SYM_WORKFLOW_RUND}"
run_fail "${TEST_NAME_BASE}-run" cylc play "${SYM_WORKFLOW_NAME}" --debug --no-detach
grep_ok 'CRITICAL - Workflow shutting down' "${WORKFLOW_RUN_DIR}/log/scheduler/"*.log
grep_ok 'unable to open database file' "${WORKFLOW_RUN_DIR}/log/scheduler/"*.log

rm -f "${SYM_WORKFLOW_RUND}"
purge
exit
