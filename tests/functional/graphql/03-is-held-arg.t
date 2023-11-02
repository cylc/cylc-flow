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
# Test workflow graphql interface
# TODO: convert to integration test
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
init_workflow "${TEST_NAME_BASE}" << __FLOW__
[meta]
    title = foo
    description = bar
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[BAZ]]
    [[foo]]
        inherit = BAZ
        script = sleep 20
__FLOW__

# run workflow
run_ok "${TEST_NAME_BASE}-run" cylc play "${WORKFLOW_NAME}"
cylc hold --after=0 "${WORKFLOW_NAME}"
sleep 1

# query workflow
TEST_NAME="${TEST_NAME_BASE}-is-held-arg"
read -r -d '' isHeld <<_args_
{
  "request_string": "
query {
  workflows {
    name
    isHeldTotal
    taskProxies(isHeld: true, graphDepth: 1) {
      id
      jobs {
        submittedTime
        startedTime
      }
    }
    familyProxies(exids: [\"*/root\"], isHeld: true, graphDepth: 1) {
      id
    }
  }
}",
  "variables": null
}
_args_
run_graphql_ok "${TEST_NAME}" "${WORKFLOW_NAME}" "${isHeld}"

# scrape workflow info from contact file
TEST_NAME="${TEST_NAME_BASE}-contact"
run_ok "${TEST_NAME_BASE}-contact" cylc get-contact "${WORKFLOW_NAME}"

# stop workflow
cylc stop --max-polls=10 --interval=2 --kill "${WORKFLOW_NAME}"

RESPONSE="${TEST_NAME_BASE}-is-held-arg.stdout"
perl -pi -e 's/("submittedTime":).*$/${1} "blargh",/' "${RESPONSE}"
perl -pi -e 's/("startedTime":).*$/${1} "blargh"/' "${RESPONSE}"

# compare to expectation
cmp_json "${TEST_NAME}-out" "$RESPONSE" << __HERE__
{
    "workflows": [
        {
            "name": "${WORKFLOW_NAME}",
            "isHeldTotal": 1,
            "taskProxies": [
                {
                    "id": "~${USER}/${WORKFLOW_NAME}//1/foo",
                    "jobs": [
                        {
                            "submittedTime": "blargh",
                            "startedTime": "blargh"
                        }
                    ]
                }
            ],
            "familyProxies": [
                {
                    "id": "~${USER}/${WORKFLOW_NAME}//1/BAZ"
                }
            ]
        }
    ]
}
__HERE__

purge
