#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test cylc monitor USER_AT_HOST interface, using cylc scan output.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduling]
    [[dependencies]]
        graph = foo
[runtime]
    [[foo]]
        script = sleep 60
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"

TEST_NAME="${TEST_NAME_BASE}-monitor-1"
run_ok "${TEST_NAME}" cylc monitor \
    $(cylc scan --color=never -n "${SUITE_NAME}") --once
grep_ok "${SUITE_NAME} - 1 task" "${TEST_NAME}.stdout"

# Same again, but force a port scan instead of looking under ~/cylc-run.
# (This also tests GitHub #2795 -"cylc scan -a" abort).
TEST_NAME="${TEST_NAME_BASE}-monitor-2"
run_ok "${TEST_NAME}" cylc monitor \
    $(cylc scan --color=never -n "${SUITE_NAME}") --once
grep_ok "${SUITE_NAME} - 1 task" "${TEST_NAME}.stdout"

cylc stop --kill "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
