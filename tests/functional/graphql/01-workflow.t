#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
# Test suite graphql interface
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# run suite
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"

# query suite
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
    newestRunaheadCyclePoint
    newestCyclePoint
    oldestCyclePoint
    reloaded
    runMode
    stateTotals
    workflowLogDir
    timeZoneInfo {
      hours
      minutes
    }
    nsDefnOrder
    states
  }
}",
  "variables": null
}
_args_
run_graphql_ok "${TEST_NAME}" "${SUITE_NAME}" "${workflowQuery}"

# scrape suite info from contact file
TEST_NAME="${TEST_NAME_BASE}-contact"
run_ok "${TEST_NAME_BASE}-contact" cylc get-contact "${SUITE_NAME}"
HOST=$(sed -n 's/CYLC_SUITE_HOST=\(.*\)/\1/p' "${TEST_NAME}.stdout")
PORT=$(sed -n 's/CYLC_SUITE_PORT=\(.*\)/\1/p' "${TEST_NAME}.stdout")
SUITE_LOG_DIR="$( cylc cat-log -m p "${SUITE_NAME}" \
    | xargs dirname )"

# stop suite
cylc stop --max-polls=10 --interval=2 --kill "${SUITE_NAME}"

# compare to expectation
cat > expected << __HERE__
{
    "workflows": [
        {
            "name": "${SUITE_NAME}",
            "status": "running",
            "statusMsg": "running to stop at 1",
            "host": "${HOST}",
            "port": ${PORT},
            "owner": "${USER}",
            "cylcVersion": "$(cylc version)",
            "meta": {
                "title": "foo",
                "description": "bar"
            },
            "newestRunaheadCyclePoint": "1",
            "newestCyclePoint": "1",
            "oldestCyclePoint": "1",
            "reloaded": false,
            "runMode": "live",
            "stateTotals": {
                "runahead": 0,
                "waiting": 0,
                "queued": 0,
                "expired": 0,
                "ready": 1,
                "submit-failed": 0,
                "submit-retrying": 0,
                "submitted": 0,
                "retrying": 0,
                "running": 0,
                "failed": 0,
                "succeeded": 0
            },
            "workflowLogDir": "${SUITE_LOG_DIR}",
            "timeZoneInfo": {
                "hours": 0,
                "minutes": 0
            },
            "nsDefnOrder": [
                "foo",
                "root"
            ],
            "states": [
                "ready"
            ]
        }
    ]
}
__HERE__
cmp_json "${TEST_NAME}-out" \
    "${TEST_NAME_BASE}-workflows.stdout" \
    "$(cat expected)"

purge_suite "${SUITE_NAME}"

exit
