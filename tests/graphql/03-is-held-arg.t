#!/bin/bash
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
cylc hold "${SUITE_NAME}"
sleep 1

# query suite
TEST_NAME="${TEST_NAME_BASE}-is-held-arg"
ID_DELIM='|'
read -r -d '' isHeld <<_args_
{
  "request_string": "
query {
  workflows {
    name
    isHeldTotal
    taskProxies(isHeld: false) {
      id
    }
    familyProxies(exids: [\"root\"], isHeld: true) {
      id
    }
  }
}",
  "variables": null
}
_args_
run_graphql_ok "${TEST_NAME}" "${SUITE_NAME}" "${isHeld}"

# scrape suite info from contact file
TEST_NAME="${TEST_NAME_BASE}-contact"
run_ok "${TEST_NAME_BASE}-contact" cylc get-contact "${SUITE_NAME}"

# stop suite
cylc stop --max-polls=10 --interval=2 --kill "${SUITE_NAME}"

# compare to expectation
cat > expected << __HERE__
{
    "workflows": [
        {
            "name": "${SUITE_NAME}",
            "isHeldTotal": 1,
            "taskProxies": [],
            "familyProxies": [
                {
                    "id": "${USER}${ID_DELIM}${SUITE_NAME}${ID_DELIM}1${ID_DELIM}BAZ"
                }
            ]
        }
    ]
}
__HERE__
cmp_json "${TEST_NAME}-out" \
    "${TEST_NAME_BASE}-is-held-arg.stdout" \
    "$(cat expected)"

purge_suite "${SUITE_NAME}"

exit
