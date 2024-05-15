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
# Test data-store pruning
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
init_workflow "${TEST_NAME_BASE}" << __FLOW__
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    final cycle point = 1
    [[graph]]
        P1 = """
a? => b? => c?
d => e
"""
[runtime]
    [[a,c,e]]
        script = true
    [[b]]
        script = false
    [[d]]
        script = """
cylc workflow-state \${CYLC_WORKFLOW_ID}//1/b:failed --interval=2
cylc pause \$CYLC_WORKFLOW_ID
"""
__FLOW__

# run workflow
run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"

cylc workflow-state "${WORKFLOW_NAME}/1/d:succeeded" --interval=2 --max-polls=60

# query workflow
TEST_NAME="${TEST_NAME_BASE}-prune-optional-break"
read -r -d '' optionalBreak <<_args_
{
  "request_string": "
query {
  workflows {
    name
    taskProxies (sort: {keys: [\"name\"]}) {
      id
      state
    }
  }
}",
  "variables": null
}
_args_
run_graphql_ok "${TEST_NAME}" "${WORKFLOW_NAME}" "${optionalBreak}"

# stop workflow
cylc stop --max-polls=10 --interval=2 --kill "${WORKFLOW_NAME}"

RESPONSE="${TEST_NAME_BASE}-prune-optional-break.stdout"

# compare to expectation
cmp_json "${TEST_NAME}-out" "$RESPONSE" << __HERE__
{
    "workflows": [
        {
            "name": "${WORKFLOW_NAME}",
            "taskProxies": [
                {
                    "id": "~${USER}/${WORKFLOW_NAME}//1/d",
                    "state": "succeeded"
                },
                {
                    "id": "~${USER}/${WORKFLOW_NAME}//1/e",
                    "state": "waiting"
                }
            ]
        }
    ]
}
__HERE__

purge
