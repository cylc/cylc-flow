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
# Test workflow info API, get_graph_raw, simple usage
. "$(dirname "$0")/test_header"
set_test_number 3

# This test relies on jobs inheriting the venv python from the scheduler.
create_test_global_config "
[platforms]
    [[localhost]]
        clean job submission environment = False
"

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
cp -r "${TEST_SOURCE_DIR}"/bin "${WORKFLOW_RUN_DIR}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
cmp_ok "${WORKFLOW_RUN_DIR}/ctb-get-graph-raw.out" <<'__OUT__'
[
    [
        [
            "t1.1",
            null,
            null,
            false,
            false
        ],
        [
            "t1.1",
            "T.1",
            null,
            false,
            false
        ],
        [
            "t1.1",
            "T.1",
            null,
            false,
            false
        ]
    ],
    {},
    [
        "t1",
        "t2",
        "t3"
    ],
    [
        "T",
        "t1"
    ]
]
__OUT__

purge
exit

TODO - the rest of these will require the same treatment
