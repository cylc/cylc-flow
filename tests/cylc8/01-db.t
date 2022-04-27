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
# Cylc 7 should not run a suite.rc workflow that was previously run with Cylc 8

. "$(dirname "$0")/test_header"
set_test_number 5

which sqlite3 > /dev/null || skip_all "sqlite3 not installed?"

SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME_BASE}"
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
mkdir -p "${SUITE_RUN_DIR}/.service"
cat > "${SUITE_RUN_DIR}/suite.rc" << __SUITERC__
[scheduling]
    initial cycle point = 2002
    [[dependencies]]
        [[[R1]]]
            graph = foo
__SUITERC__
# Recreate Cylc 8 database
sqlite3 "${SUITE_RUN_DIR}/.service/db" < "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/db.sqlite3"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

MSG="Suite Cylc version .* is incompatible"

TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_fail "$TEST_NAME" cylc run "$SUITE_NAME"
grep_ok "$MSG" "${TEST_NAME}.stderr"

TEST_NAME="${TEST_NAME_BASE}-restart"
suite_run_fail "$TEST_NAME" cylc restart "$SUITE_NAME"
grep_ok "$MSG" "${TEST_NAME}.stderr"

purge_suite "$SUITE_NAME"
exit
