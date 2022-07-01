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
# -----------------------------------------------------------------------------
# Test cleaning multiple run dirs

. "$(dirname "$0")/test_header"
set_test_number 14

for _ in 1 2; do
    install_workflow "$TEST_NAME_BASE" basic-workflow true
done

exists_ok "${WORKFLOW_RUN_DIR}/run1"
exists_ok "${WORKFLOW_RUN_DIR}/run2"

# Test trying to clean multiple run dirs without --yes fails:
run_fail "${TEST_NAME_BASE}-no" cylc clean "$WORKFLOW_NAME"
exists_ok "${WORKFLOW_RUN_DIR}/run1"
exists_ok "${WORKFLOW_RUN_DIR}/run2"


# Should work with --yes:
run_ok "${TEST_NAME_BASE}-yes" cylc clean -y "$WORKFLOW_NAME"
exists_fail "${WORKFLOW_RUN_DIR}/run1"
exists_fail "${WORKFLOW_RUN_DIR}/run2"

# Should continue cleaning a list of worflows even if one fails.

for _ in 1 2; do
    install_workflow "$TEST_NAME_BASE" basic-workflow true
done

exists_ok "${WORKFLOW_RUN_DIR}/run1"
exists_ok "${WORKFLOW_RUN_DIR}/run2"

mkdir "${WORKFLOW_RUN_DIR}/run1/.service"
touch "${WORKFLOW_RUN_DIR}/run1/.service/db"  # corrupted db!

TEST_NAME="${TEST_NAME_BASE}-yes-no" 
run_ok "${TEST_NAME}" \
    cylc clean -y "$WORKFLOW_NAME/run1" "$WORKFLOW_NAME/run2"

grep_ok "Cannot clean .*/run1" "${TEST_NAME}.stderr" -e

exists_ok "${WORKFLOW_RUN_DIR}/run1"
exists_fail "${WORKFLOW_RUN_DIR}/run2"

purge
