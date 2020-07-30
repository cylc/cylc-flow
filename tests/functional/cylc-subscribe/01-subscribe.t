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
# Test `cylc subscribe`.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = foo => bar => wiq => qux
[runtime]
    [[foo, bar, wiq, qux]]
        script = sleep 2
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"

TEST_NAME="${TEST_NAME_BASE}-subscribe-1"
run_ok "${TEST_NAME}" cylc subscribe --once --topics="workflow" "${SUITE_NAME}"
grep_ok "running" "${TEST_NAME}.stdout"

TEST_NAME="${TEST_NAME_BASE}-subscribe-2"
run_ok "${TEST_NAME}" cylc subscribe --once --topics="workflow" "${SUITE_NAME}"
grep_ok "running" "${TEST_NAME}.stdout"

cylc stop --kill --max-polls=20 --interval=1 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
