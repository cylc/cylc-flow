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

# Originally (Cylc 7): test workflow-state query on a waiting task - GitHub #2440.
# Now (Cylc 8): test result of a failed workflow-state query.

. "$(dirname "$0")/test_header"
set_test_number 4

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach "${WORKFLOW_NAME}"

TEST_NAME=${TEST_NAME_BASE}-query
run_fail "${TEST_NAME}" cylc workflow-state "${WORKFLOW_NAME}//2013/foo:x" --max-polls=1

grep_ok "failed after 1 polls" "${TEST_NAME}.stderr"

purge
