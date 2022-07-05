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
#------------------------------------------------------------------------

# test the output of `cylc play` with different `--format` options

. "$(dirname "$0")/test_header"

set_test_number 8

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[dependencies]]
        R1 = foo
__FLOW_CONFIG__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"

# format=plain
TEST_NAME="${TEST_NAME_BASE}-run-format-plain"
workflow_run_ok "${TEST_NAME}" cylc play --format plain "${WORKFLOW_NAME}"
grep_ok "Copyright" "${TEST_NAME}.stdout"
grep_ok "${WORKFLOW_NAME}:" "${TEST_NAME}.stdout"

poll_workflow_running
poll_workflow_stopped
delete_db

# format=json
TEST_NAME="${TEST_NAME_BASE}-run-format-json"
workflow_run_ok "${TEST_NAME}" cylc play --format json "${WORKFLOW_NAME}"
run_ok "${TEST_NAME}-fields" python3 -c '
import json
import sys
data = json.load(open(sys.argv[1], "r"))
print(list(sorted(data)), file=sys.stderr)
assert list(sorted(data)) == [
    "host", "pid", "pub_url", "url", "workflow"]
' "${TEST_NAME}.stdout"

poll_workflow_running
poll_workflow_stopped
delete_db

# quiet
TEST_NAME="${TEST_NAME_BASE}-run-quiet"
workflow_run_ok "${TEST_NAME}" cylc play --quiet "${WORKFLOW_NAME}"
grep_ok "${WORKFLOW_NAME}:" "${TEST_NAME}.stdout"

poll_workflow_running
poll_workflow_stopped
purge
