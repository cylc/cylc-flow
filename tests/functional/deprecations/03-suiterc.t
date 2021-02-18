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
set_test_number 7

init_suiterc() {
    local TEST_NAME="$1"
    local FLOW_CONFIG="${2:--}"
    SUITE_NAME="${CYLC_TEST_REG_BASE}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME}"
    SUITE_RUN_DIR="$RUN_DIR/$SUITE_NAME"
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
grep_ok "The filename \"suite.rc\" is deprecated in favour of \"flow.cylc\". Symlink created." "${TEST_NAME_BASE}-validate.stderr" 
TEST_NAME="${TEST_NAME_BASE}-install"
run_ok "${TEST_NAME}" cylc install --flow-name="${SUITE_NAME}" --no-run-name
cd "${SUITE_RUN_DIR}" || exit 1
exists_ok "flow.cylc"
cd "${TEST_DIR}" || exit 1
rm -rf "${TEST_DIR:?}/${SUITE_NAME}/"
purge

# Test install upgrades suite.rc and logs deprecation notification

init_suiterc "${TEST_NAME_BASE}" <<'__FLOW__'
[scheduling]
    [[graph]]
        R1 = foo => bar
__FLOW__


TEST_NAME="${TEST_NAME_BASE}-install"
run_ok "${TEST_NAME}" cylc install --flow-name="${SUITE_NAME}" --no-run-name
cd "${SUITE_RUN_DIR}" || exit 1
exists_ok "flow.cylc"
INSTALL_LOG="$(find "${SUITE_RUN_DIR}/log/install" -type f -name '*.log')"
grep_ok "The filename \"suite.rc\" is deprecated in favour of \"flow.cylc\". Symlink created." "${INSTALL_LOG}" 
cd "${TEST_DIR}" || exit 1
rm -rf "${TEST_DIR:?}/${SUITE_NAME}/"
purge
