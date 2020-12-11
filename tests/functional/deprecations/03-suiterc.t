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
#------------------------------------------------------------------------------
# Test backwards compatibility for suite.rc files

. "$(dirname "$0")/test_header"
set_test_number 3

init_suiterc() {
    local TEST_NAME="$1"
    local FLOW_CONFIG="${2:--}"
    SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME}"
    mkdir -p "${TEST_DIR}/${SUITE_NAME}/"
    cat "${FLOW_CONFIG}" >"${TEST_DIR}/${SUITE_NAME}/suite.rc"
    cd "${TEST_DIR}/${SUITE_NAME}" || exit
}

init_suiterc "${TEST_NAME_BASE}" <<'__FLOW__'
[scheduling]
    [[graph]]
        R1 = foo => bar
__FLOW__

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate .

TEST_NAME="${TEST_NAME_BASE}-install"
run_ok "${TEST_NAME}" cylc install --flow-name="${SUITE_NAME}" --no-run-name

exists_ok "flow.cylc"

purge
