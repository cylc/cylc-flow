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
# Test no stall when task pool has succeeded tasks only.
. "$(dirname "$0")/test_header"
set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
poll_suite_stopped

grep_ok '\[t1\.1\] .*succeeded' "${SUITE_RUN_DIR}/log/suite/log"

run_fail "${TEST_NAME_BASE}-not-stalled" \
    grep -q -F 'WARNING - suite stalled' "${SUITE_RUN_DIR}/log/suite/log"
purge
exit
