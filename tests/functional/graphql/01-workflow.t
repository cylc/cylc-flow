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
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# run workflow
run_ok "${TEST_NAME_BASE}-run" cylc play --pause "${WORKFLOW_NAME}"

# query workflow
TEST_NAME="${TEST_NAME_BASE}-workflows"
read -r -d '' workflowQuery <<_args_
{
  "request_string": "
query {
  workflows {
    name
    status
    statusMsg
    host
    port
    owner
    cylcVersion
    meta {
      title
      description
    }
    newestActiveCyclePoint
    oldestActiveCyclePoint
    reloaded
    runMode
    nEdgeDistance
    stateTotals
    workflowLogDir
    timeZoneInfo {
      hours
      minutes
    }
    nsDefOrder
    states
    latestStateTasks (states: [\"waiting\"])
  }
}",
  "variables": null
}
_args_
run_graphql_ok "${TEST_NAME}" "${WORKFLOW_NAME}" "${workflowQuery}"

# scrape workflow info from contact file
TEST_NAME="${TEST_NAME_BASE}-contact"
run_ok "${TEST_NAME_BASE}-contact" cylc get-contact "${WORKFLOW_NAME}"
HOST=$(sed -n 's/CYLC_WORKFLOW_HOST=\(.*\)/\1/p' "${TEST_NAME}.stdout")
PORT=$(sed -n 's/CYLC_WORKFLOW_PORT=\(.*\)/\1/p' "${TEST_NAME}.stdout")
WORKFLOW_LOG_DIR="$( cylc cat-log -m p "${WORKFLOW_NAME}" \
    | xargs dirname )"

# stop workflow
cylc stop --max-polls=10 --interval=2 --kill "${WORKFLOW_NAME}"

# Compare to expectation
# Note: One active cycle point on starting paused
#   (runahead tasks are now in the main scheduler task pool)
cmp_json "${TEST_NAME}-out" "${TEST_NAME_BASE}-workflows.stdout" << __HERE__
{
    "workflows": [
        {
            "name": "${WORKFLOW_NAME}",
            "status": "paused",
            "statusMsg": "paused",
            "host": "${HOST}",
            "port": ${PORT},
            "owner": "${USER}",
            "cylcVersion": "$(cylc version)",
            "meta": {
                "title": "foo",
                "description": "bar"
            },
            "newestActiveCyclePoint": "20210101T0000Z",
            "oldestActiveCyclePoint": "20210101T0000Z",
            "reloaded": false,
            "runMode": "live",
            "nEdgeDistance": 1,
            "stateTotals": {
                "waiting": 1,
                "expired": 0,
                "preparing": 0,
                "submit-failed": 0,
                "submitted": 0,
                "running": 0,
                "failed": 0,
                "succeeded": 0
            },
            "workflowLogDir": "${WORKFLOW_LOG_DIR}",
            "timeZoneInfo": {
                "hours": 0,
                "minutes": 0
            },
            "nsDefOrder": [
                "foo",
                "root"
            ],
            "states": ["waiting"],
            "latestStateTasks": {
                "waiting": ["20210101T0000Z/foo"]
            }
        }
    ]
}
__HERE__

purge

exit
