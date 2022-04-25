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
# Test workflow shuts down with error on missing port file
. "$(dirname "$0")/test_header"

set_test_number 3

OPT_SET=
create_test_global_config "" "
[scheduler]
    [[main loop]]
        # plugins = health check
        [[[health check]]]
            interval = PT11S"
OPT_SET='-s GLOBALCFG=True'

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-validate" cylc validate ${OPT_SET} "${WORKFLOW_NAME}"
# shellcheck disable=SC2086
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --no-detach --abort-if-any-task-fails ${OPT_SET} "${WORKFLOW_NAME}"
SRVD="$RUN_DIR/${WORKFLOW_NAME}/.service"
LOGD="$RUN_DIR/${WORKFLOW_NAME}/log"
grep_ok \
    "${SRVD}/contact: contact file corrupted/modified and may be left" \
    "${LOGD}/scheduler/log"
purge
exit
