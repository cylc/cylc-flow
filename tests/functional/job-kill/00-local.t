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
# Test kill local jobs.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 10
#-------------------------------------------------------------------------------
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-ps"
for DIR in "${WORKFLOW_RUN_DIR}"/work/*/t*; do
    run_fail "${TEST_NAME}.$(basename "$DIR")" ps "$(cat "${DIR}/file")"
done
N=0
for FILE in "${WORKFLOW_RUN_DIR}"/log/job/*/t*/01/job.status; do
    run_fail "${TEST_NAME}-status-$((++N))" \
        ps "$(awk -F= '$1 == "CYLC_JOB_PID" {print $2}' "$FILE")"
done
#-------------------------------------------------------------------------------
purge
exit
