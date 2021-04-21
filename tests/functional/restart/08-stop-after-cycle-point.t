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
set_test_number 9
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

# Check that the config stop point works.
workflow_run_ok "${TEST_NAME_BASE}-no-cmd-line-opts" \
    cylc play --no-detach "${WORKFLOW_NAME}"
WORKFLOWLOG="${WORKFLOW_RUN_DIR}/log/workflow/log"
# Check task hello@stopped cylc point is spawned but never submitted
grep_fail "\[hello.19700101T0100Z\] -submit-num=01" "${WORKFLOWLOG}"

delete_db

# Check that the command line stop point works.
workflow_run_ok "${TEST_NAME_BASE}-cmd-line-stop" \
    cylc play --no-detach --stopcp=19700101T0100Z "${WORKFLOW_NAME}"
grep_fail "\[hello.19700101T0200Z\] -submit-num=01" "${WORKFLOWLOG}"

# Check that stop is preserved on restart ...
workflow_run_ok "${TEST_NAME_BASE}-cmd-line-stop" \
    cylc play --no-detach "${WORKFLOW_NAME}"
grep_fail "\[hello.19700101T0200Z\] -submit-num=01" "${WORKFLOWLOG}"

# ... unless we say otherwise.
workflow_run_ok "${TEST_NAME_BASE}-cmd-line-stop" \
    cylc play --no-detach --stopcp=ignore "${WORKFLOW_NAME}"
grep_ok "\[hello.19700101T0200Z\] -submit-num=01" "${WORKFLOWLOG}"

purge
