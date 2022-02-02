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
# Test pipefail cylc/cylc-flow#1783
. "$(dirname "$0")/test_header"

set_test_number 6
install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}-validate" cylc validate "${WORKFLOW_NAME}"
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_fail "${TEST_NAME_BASE}-run" \
    cylc play --no-detach --debug --reference-test "${WORKFLOW_NAME}"

# Make sure status files are in place
T1_STATUS_FILE="${WORKFLOW_RUN_DIR}/log/job/1/t1/01/job.status"
contains_ok "${T1_STATUS_FILE}" <<'__STATUS__'
CYLC_JOB_EXIT=ERR
__STATUS__
grep_ok 'CYLC_JOB_EXIT_TIME=' "${T1_STATUS_FILE}"

T2_STATUS_FILE="${WORKFLOW_RUN_DIR}/log/job/1/t2/01/job.status"
contains_ok "${T2_STATUS_FILE}" <<'__STATUS__'
CYLC_JOB_EXIT=EXIT
__STATUS__
grep_ok 'CYLC_JOB_EXIT_TIME=' "${T2_STATUS_FILE}"

purge
exit
