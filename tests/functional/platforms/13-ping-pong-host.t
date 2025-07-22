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
#-----------------------------------------------------------------------------

# If a task has [remote]host=$(subshell) this should be evaluated
# every time the task is run.
# https://github.com/cylc/cylc-flow/issues/6808
export REQUIRE_PLATFORM='loc:remote'

. "$(dirname "$0")/test_header"

set_test_number 3

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play "${WORKFLOW_NAME}" --debug --no-detach

named_grep_ok "1/remote_task submits to ${CYLC_TEST_PLATFORM}" \
    "\[1/remote_task/01:preparing\] submitted to ${CYLC_TEST_HOST}" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log"

named_grep_ok "2/remote_task submits to localhost" \
    "\[2/remote_task/01:preparing\] submitted to localhost" \
    "${WORKFLOW_RUN_DIR}/log/scheduler/log"

purge
