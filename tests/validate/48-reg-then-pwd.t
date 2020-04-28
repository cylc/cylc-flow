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
# Test validation order, registered suites before current working directory.
. "$(dirname "$0")/test_header"
set_test_number 2

SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"

mkdir -p 'good' "${SUITE_NAME}"
cat >'good/suite.rc' <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = t0
[runtime]
    [[t0]]
        script = true
__SUITE_RC__
cat >"${SUITE_NAME}/suite.rc" <<'__SUITE_RC__'
[scheduling]
    [[graph]]
        R1 = t0
[runtime]
    [[t0]]
        scribble = true
__SUITE_RC__

# This should validate bad suite under current directory
run_fail "${TEST_NAME_BASE}" cylc validate "${SUITE_NAME}"

# This should validate registered good suite
cylc register "${SUITE_NAME}" "${PWD}/good"
run_ok "${TEST_NAME_BASE}" cylc validate "${SUITE_NAME}"

purge_suite "${SUITE_NAME}"
exit
