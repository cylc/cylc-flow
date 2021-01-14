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
# Run a workflow with ``cylc run --host=somewhere-else``
export REQUIRE_PLATFORM='loc:remote fs:shared runner:background'
. "$(dirname "$0")/test_header"
set_test_number 2

# shellcheck disable=SC2016
init_suite "${TEST_NAME_BASE}" <<< '
# A total non-entity workflow - just something to run.
[scheduling]
    initial cycle point = 2020
    [[graph]]
        R1 = Aleph

[runtime]
    [[Aleph]]
'

suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --host="${CYLC_TEST_HOST}" --no-detach

grep_ok "Suite server:.*${CYLC_TEST_HOST}" "${SUITE_RUN_DIR}/log/suite/log"

purge
exit
