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
# Test environment filtering
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 13
#-------------------------------------------------------------------------------
# a test workflow that uses environment filtering:
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1 = "foo & bar & baz & qux"
[runtime]
    [[root]]
        [[[environment]]]
            FOO = foo
            BAR = bar
            BAZ = baz
    [[foo]]
        [[[environment filter]]]
            include = FOO, BAR
        [[[environment]]]
            QUX = qux
    [[bar]]
        [[[environment filter]]]
            include = FOO, BAR
            exclude = FOO
    [[baz]]
        [[[environment filter]]]
            exclude = FOO, BAR
        [[[environment]]]
            QUX = qux
    [[qux]]
        [[[environment]]]
            QUX = qux
__FLOW_CONFIG__
#-------------------------------------------------------------------------------
# check validation
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
# check that config retrieves only the filtered environment
TEST_NAME=${TEST_NAME_BASE}-config

run_ok "${TEST_NAME}" cylc config --item='[runtime][foo]environment' "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__OUT__
FOO = foo
BAR = bar
__OUT__
cmp_ok "${TEST_NAME}.stderr" - </dev/null

run_ok "${TEST_NAME}" cylc config --item='[runtime][bar]environment' "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__OUT__
BAR = bar
__OUT__
cmp_ok "${TEST_NAME}.stderr" - </dev/null

run_ok "${TEST_NAME}" cylc config --item='[runtime][baz]environment' "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__OUT__
BAZ = baz
QUX = qux
__OUT__
cmp_ok "${TEST_NAME}.stderr" - </dev/null

run_ok "${TEST_NAME}" cylc config --item='[runtime][qux]environment' "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__OUT__
FOO = foo
BAR = bar
BAZ = baz
QUX = qux
__OUT__
cmp_ok "${TEST_NAME}.stderr" - </dev/null

#-------------------------------------------------------------------------------
purge
exit
