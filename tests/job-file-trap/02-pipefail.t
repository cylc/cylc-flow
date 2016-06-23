#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test pipefail cylc/cylc#1783
. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
TEST_NAME=$TEST_NAME_BASE-validate
run_ok "${TEST_NAME}-validate" cylc validate "${SUITE_NAME}"
TEST_NAME=$TEST_NAME_BASE-run
suite_run_fail "${TEST_NAME_BASE}-run" \
    cylc run --no-detach --reference-test "${SUITE_NAME}"
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"

# Make sure t1.1.1's status file is in place
T1_STATUS_FILE="${SUITE_RUN_DIR}/log/job/1/t1/01/job.status"
contains_ok "${T1_STATUS_FILE}" <<'__STATUS__'
CYLC_JOB_EXIT=EXIT
CYLC_JOB_EXIT=ERR
__STATUS__

purge_suite "${SUITE_NAME}"
exit
