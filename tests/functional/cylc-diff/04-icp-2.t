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
# Test for "cylc diff --icp=CYCLE_POINT", override.
. "$(dirname "$0")/test_header"

set_test_number 3

init_suite "${TEST_NAME_BASE}-1" <<'__FLOW_CONFIG__'
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
SUITE_NAME1="${SUITE_NAME}"
init_suite "${TEST_NAME_BASE}-2" <<'__FLOW_CONFIG__'
[scheduler]
    UTC mode = True
[scheduling]
    initial cycle point = 2016
    [[graph]]
        R1 = food => barley
[runtime]
    [[food, barley]]
        script = true
__FLOW_CONFIG__
# shellcheck disable=SC2153
SUITE_NAME2="${SUITE_NAME}"

run_ok "${TEST_NAME_BASE}" \
    cylc diff --icp=2020 "${SUITE_NAME1}" "${SUITE_NAME2}"
cmp_ok "${TEST_NAME_BASE}.stdout" <<__OUT__
Parsing ${SUITE_NAME1} (${RUN_DIR}/${SUITE_NAME1}/flow.cylc)
Parsing ${SUITE_NAME2} (${RUN_DIR}/${SUITE_NAME2}/flow.cylc)
Suite definitions ${SUITE_NAME1} and ${SUITE_NAME2} differ

2 items only in ${SUITE_NAME1} (<)

   [runtime] [[foo]]
 <   script = true

   [runtime] [[bar]]
 <   script = true

2 items only in ${SUITE_NAME2} (>)

   [runtime] [[food]]
 >   script = true

   [runtime] [[barley]]
 >   script = true

2 common items differ ${SUITE_NAME1}(<) ${SUITE_NAME2}(>)

   [scheduling] [[graph]]
 <   R1 = foo => bar
 >   R1 = food => barley

   [visualization] [[node groups]]
 <   root = ['root', 'foo', 'bar']
 >   root = ['root', 'food', 'barley']
__OUT__
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

purge "${SUITE_NAME1}"
purge "${SUITE_NAME2}"
exit
