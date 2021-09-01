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
# Test workflow info API, get_graph_raw, simple usage, non-digit ICP
. "$(dirname "$0")/test_header"
set_test_number 3

# This test relies on jobs inheriting the venv python from the scheduler.
create_test_global_config "
[platforms]
    [[localhost]]
        clean job submission environment = False
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
cmp_json "${TEST_NAME_BASE}-out" \
    "${WORKFLOW_RUN_DIR}/ctb-get-graph-raw.out" <<'__OUT__'
[
    [
        [
            "t1.20200202T0000Z",
            null,
            null,
            false,
            false
        ],
        [
            "t1.20200202T0000Z",
            "t1.20200203T0000Z",
            null,
            false,
            false
        ]
    ],
    {},
    [
        "t1"
    ],
    [
        "t1"
    ]
]
__OUT__

purge
exit
