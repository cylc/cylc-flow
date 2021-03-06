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
# Test for "cylc diff" with 2 suites pointing to same "flow.cylc".
. "$(dirname "$0")/test_header"

set_test_number 3

cat >'flow.cylc' <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1 = foo => bar
[runtime]
    [[foo, bar]]
        script = true
__FLOW_CONFIG__
init_suite "${TEST_NAME_BASE}-1" "${PWD}/flow.cylc"
# shellcheck disable=SC2153
SUITE_NAME1="${SUITE_NAME}"
# shellcheck disable=SC2153
SUITE_NAME2="${SUITE_NAME1%1}2"
cylc install --flow-name="${SUITE_NAME2}" --directory="${TEST_DIR}/${SUITE_NAME1}" --no-run-name 2>'/dev/null'

run_ok "${TEST_NAME_BASE}" cylc diff "${SUITE_NAME1}" "${SUITE_NAME2}"
cmp_ok "${TEST_NAME_BASE}.stdout" <<__OUT__
Parsing ${SUITE_NAME1} (${RUN_DIR}/${SUITE_NAME1}/flow.cylc)
Parsing ${SUITE_NAME2} (${RUN_DIR}/${SUITE_NAME2}/flow.cylc)
Suite definitions ${SUITE_NAME1} and ${SUITE_NAME2} are identical
__OUT__
cmp_ok "${TEST_NAME_BASE}.stderr" <'/dev/null'

purge "${SUITE_NAME1}"
purge "${SUITE_NAME2}"
exit
