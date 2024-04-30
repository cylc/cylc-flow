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
# Basic test for "cylc diff".
. "$(dirname "$0")/test_header"

set_test_number 3

init_workflow "${TEST_NAME_BASE}-1" <<'__FLOW_CONFIG__'
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
[scheduling]
    [[graph]]
        R1 = food => barley
[runtime]
    [[food, barley]]
        script = true
__FLOW_CONFIG__
# shellcheck disable=SC2153
WORKFLOW_NAME2="${WORKFLOW_NAME}"

run_ok "${TEST_NAME_BASE}" cylc diff "${WORKFLOW_NAME1}" "${WORKFLOW_NAME2}"
cmp_ok "${TEST_NAME_BASE}.stdout" <<__OUT__
Parsing ${WORKFLOW_NAME1} (${RUN_DIR}/${WORKFLOW_NAME1}/flow.cylc)
Parsing ${WORKFLOW_NAME2} (${RUN_DIR}/${WORKFLOW_NAME2}/flow.cylc)
Workflow definitions ${WORKFLOW_NAME1} and ${WORKFLOW_NAME2} differ

2 items only in ${WORKFLOW_NAME1} (<)

   [runtime] [[foo]]
 <   script = true
 <   completion = succeeded

   [runtime] [[bar]]
 <   script = true
 <   completion = succeeded

2 items only in ${WORKFLOW_NAME2} (>)

   [runtime] [[food]]
 >   script = true
 >   completion = succeeded

   [runtime] [[barley]]
 >   script = true
 >   completion = succeeded

1 common items differ ${WORKFLOW_NAME1}(<) ${WORKFLOW_NAME2}(>)

   [scheduling] [[graph]]
 <   R1 = foo => bar
 >   R1 = food => barley
__OUT__
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

purge "${WORKFLOW_NAME1}"
purge "${WORKFLOW_NAME2}"
exit
