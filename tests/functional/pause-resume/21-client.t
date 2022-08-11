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
# Test resume paused workflow using the "cylc client" command.
. "$(dirname "$0")/test_header"
set_test_number 3
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
cylc play --reference-test --pause --debug --no-detach "${WORKFLOW_NAME}" \
    1>"${TEST_NAME_BASE}.out" 2>&1 &
CYLC_RUN_PID=$!
poll_workflow_running

read -r -d '' resume <<_args_
{"request_string": "
mutation {
  resume(workflows: [\"${WORKFLOW_NAME}\"]){
    results
  }
}
",
"variables": null}
_args_

# shellcheck disable=SC2086
run_ok "${TEST_NAME_BASE}-client" \
    cylc client "${WORKFLOW_NAME}" 'graphql' < <(echo ${resume})
run_ok "${TEST_NAME_BASE}-run" wait "${CYLC_RUN_PID}"
purge
exit
