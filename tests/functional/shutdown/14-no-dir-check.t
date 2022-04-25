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
# Test workflow shuts down with error on missing run directory
. "$(dirname "$0")/test_header"
set_test_number 3
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

create_test_global_config "" "
[scheduler]
    [[main loop]]
        [[[health check]]]
            interval = PT10S"
OPT_SET='-s GLOBALCFG=True'

# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" cylc validate ${OPT_SET} "${WORKFLOW_NAME}"
# Workflow run directory is now a symbolic link, so we can easily delete it.
SYM_WORKFLOW_RUND="${WORKFLOW_RUN_DIR}-sym"
SYM_WORKFLOW_NAME="${WORKFLOW_NAME}-sym"
ln -s "$(basename "${WORKFLOW_NAME}")" "${SYM_WORKFLOW_RUND}"
# shellcheck disable=SC2086
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --no-detach --abort-if-any-task-fails ${OPT_SET} "${SYM_WORKFLOW_NAME}"
# Possible failure modes:
# - health check detects missing run directory
# - DB housekeeping cannot access DB because run directory missing
# - (TODO: if other failure modes show up, add to the list here!)
FAIL1="Workflow run directory does not exist: ${SYM_WORKFLOW_RUND}"
FAIL2="sqlite3.OperationalError: unable to open database file"
grep_ok "(${FAIL1}|${FAIL2})" "${WORKFLOW_RUN_DIR}/log/scheduler/"*.log -E
rm -f "${SYM_WORKFLOW_RUND}"
purge
exit
