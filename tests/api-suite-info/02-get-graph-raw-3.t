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
# Test suite info API, get_graph_raw, simple usage
. "$(dirname "$0")/test_header"
set_test_number 3

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
cmp_json "${TEST_NAME_BASE}-out" \
    "${SUITE_RUN_DIR}/ctb-get-graph-raw.out" <<'__OUT__'
[
    [
        [
            "t1.2020", 
            null, 
            null, 
            false, 
            false
        ], 
        [
            "t1.2020", 
            "t1.2021", 
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

purge_suite "${SUITE_NAME}"
exit
