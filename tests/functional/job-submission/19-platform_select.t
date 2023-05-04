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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test recovery of a failed host select command for a group of tasks.
. "$(dirname "$0")/test_header"
set_test_number 6

install_workflow "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

logfile="${WORKFLOW_RUN_DIR}/log/scheduler/log"


# Check that host = $(cmd) is correctly evaluated
grep_ok \
    "1/host_subshell.* evaluated as improbable host name$" \
    "${logfile}"
grep_ok \
    "1/localhost_subshell.* evaluated as localhost$" \
    "${logfile}"

# Check that host = `cmd` is correctly evaluated
grep_ok \
    "1/host_subshell_backticks.* evaluated as improbable host name$" \
    "${logfile}"

# Check that platform = $(cmd) correctly evaluated
grep_ok \
    "1/platform_subshell.* evaluated as improbable platform name$" \
    "${logfile}"

purge
