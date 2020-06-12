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
# Test kill local jobs.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 10
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-ps
for DIR in "${SUITE_RUN_DIR}"/work/*/t*; do
    run_fail "${TEST_NAME}.$(basename "$DIR")" ps "$(cat "${DIR}/file")"
done
N=0
for FILE in "${SUITE_RUN_DIR}"/log/job/*/t*/01/job.status; do
    run_fail "${TEST_NAME}-status-$((++N))" \
        ps "$(awk -F= '$1 == "CYLC_JOB_PID" {print $2}' "$FILE")"
done
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
