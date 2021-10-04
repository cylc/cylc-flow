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
#------------------------------------------------------------------------------
# Test backwards compatibility for suite.rc files

. "$(dirname "$0")/test_header"
set_test_number 5

init_suiterc() {
    local TEST_NAME="$1"
    local FLOW_CONFIG="${2:--}"
    WORKFLOW_NAME="${CYLC_TEST_REG_BASE}/${TEST_SOURCE_DIR_BASE}/${TEST_NAME}"
    WORKFLOW_RUN_DIR="$RUN_DIR/$WORKFLOW_NAME"
    mkdir -p "${TEST_DIR}/${WORKFLOW_NAME}/"
    cat "${FLOW_CONFIG}" >"${TEST_DIR}/${WORKFLOW_NAME}/suite.rc"
    cd "${TEST_DIR}/${WORKFLOW_NAME}" || exit
}

init_suiterc "${TEST_NAME_BASE}" <<'__FLOW__'
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = foo => bar
__FLOW__

MSG=$(python -c 'from cylc.flow.workflow_files import SUITERC_DEPR_MSG;
print(SUITERC_DEPR_MSG)')

TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate .
grep_ok "$MSG" "${TEST_NAME_BASE}-validate.stderr"

# Test install suite.rc
# See also tests/functional/cylc-install/00-simple.t
TEST_NAME="${TEST_NAME_BASE}-install-after-validate"
run_ok "${TEST_NAME}" cylc install --flow-name="${WORKFLOW_NAME}" --no-run-name

cd "${WORKFLOW_RUN_DIR}" || exit 1
exists_ok "flow.cylc"

TEST_NAME="flow.cylc-readlink"
readlink "flow.cylc" > "${TEST_NAME}.out"
cmp_ok "${TEST_NAME}.out" <<< "suite.rc"

cd "${TEST_DIR}" || exit 1
rm -rf "${TEST_DIR:?}/${WORKFLOW_NAME}/"
purge
