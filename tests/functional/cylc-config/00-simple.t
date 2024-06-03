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
# Test cylc config
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 19
#-------------------------------------------------------------------------------
init_workflow "${TEST_NAME_BASE}" "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/flow.cylc"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-all"
run_ok "${TEST_NAME}" cylc config -d "${WORKFLOW_NAME}"
mkdir tmp_src
cp "${TEST_NAME}.stdout" tmp_src/flow.cylc
run_ok "${TEST_NAME}-validate" cylc validate --check-circular ./tmp_src
cmp_ok "${TEST_NAME}.stderr" <'/dev/null'
rm -rf tmp_src
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-section1"
run_ok "${TEST_NAME}" cylc config -d --item=[scheduling] "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" "$TEST_SOURCE_DIR/${TEST_NAME_BASE}/section1.stdout"
cmp_ok "${TEST_NAME}.stderr" - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-section1-section"
run_ok "${TEST_NAME}" cylc config -d --item=[scheduling][graph] "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__OUT__
R1 = OPS:finish-all => VAR
__OUT__
cmp_ok "${TEST_NAME}.stderr" - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-section1-section-option"
run_ok "${TEST_NAME}" \
    cylc config -d --item=[scheduling][graph]R1 "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" - <<__OUT__
OPS:finish-all => VAR
__OUT__
cmp_ok "${TEST_NAME}.stderr" - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-section2"
run_ok "${TEST_NAME}" cylc config -d --item=[runtime] "${WORKFLOW_NAME}"
cmp_ok "${TEST_NAME}.stdout" "$TEST_SOURCE_DIR/${TEST_NAME_BASE}/section2.stdout"
cmp_ok "${TEST_NAME}.stderr" - </dev/null
#-------------------------------------------------------------------------------
# Basic test that --print-hierarchy works
TEST_NAME="${TEST_NAME_BASE}-hierarchy"
run_ok "${TEST_NAME}-global" cylc config -d --print-hierarchy
run_ok "${TEST_NAME}-all" cylc config -d --print-hierarchy "${WORKFLOW_NAME}"
# The two should be same with last line of latter removed
cmp_ok "${TEST_NAME}-global.stdout" <<< "$( sed '$d' "${TEST_NAME}-all.stdout" )"
# The last line should be the workflow run dir
sed '$!d' "${TEST_NAME}-all.stdout" > "flow_path.out"
cmp_ok "flow_path.out" <<< "${WORKFLOW_RUN_DIR}/flow.cylc"

purge
exit
