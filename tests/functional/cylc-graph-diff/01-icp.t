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
# Test for "cylc graph-diff WORKFLOW1 WORKFLOW2 -- ICP".
. "$(dirname "$0")/test_header"

set_test_number 3

init_workflow "${TEST_NAME_BASE}-1" <<'__FLOW_CONFIG__'
[scheduler]
    UTC mode = True
[scheduling]
    [[graph]]
        R1 = foo => bar
[runtime]
    [[foo, bar]]
        script = true
__FLOW_CONFIG__
# shellcheck disable=SC2153
WORKFLOW_NAME1="${WORKFLOW_NAME}"
init_workflow "${TEST_NAME_BASE}-2" <<'__FLOW_CONFIG__'
[scheduler]
    UTC mode = True
[scheduling]
    [[graph]]
        R1 = food => barley
[runtime]
    [[food, barley]]
        script = true
__FLOW_CONFIG__
# shellcheck disable=SC2153
WORKFLOW_NAME2="${WORKFLOW_NAME}"

run_fail "${TEST_NAME_BASE}" \
    cylc graph "${WORKFLOW_NAME1}" --diff "${WORKFLOW_NAME2}" --icp='20200101T0000Z'
contains_ok "${TEST_NAME_BASE}.stdout" <<__OUT__
-edge "foo.20200101T0000Z" "bar.20200101T0000Z"
+edge "food.20200101T0000Z" "barley.20200101T0000Z"
 graph
-node "bar.20200101T0000Z" "bar\n20200101T0000Z"
-node "foo.20200101T0000Z" "foo\n20200101T0000Z"
+node "barley.20200101T0000Z" "barley\n20200101T0000Z"
+node "food.20200101T0000Z" "food\n20200101T0000Z"
__OUT__
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

purge "${WORKFLOW_NAME1}"
purge "${WORKFLOW_NAME2}"
exit
