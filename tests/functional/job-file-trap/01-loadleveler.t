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
#-------------------------------------------------------------------------------
# Test whether job vacation trap is included in a loadleveler job or not.
# A job for a task with the restart=yes directive will have the trap.
# This does not test loadleveler job vacation itself, because the test will
# require a site admin to pre-empt a job.
# TODO Check this test on a dockerized system or VM.
export REQUIRE_PLATFORM="runner:loadleveler"
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
run_ok "${TEST_NAME}" cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
sleep 5
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-t1.1"
T1_JOB_FILE="${SUITE_RUN_DIR}/log/job/1/t1/01/job"
exists_ok "${T1_JOB_FILE}"
run_fail "${TEST_NAME}" grep -q -e '^CYLC_VACATION_SIGNALS' "${T1_JOB_FILE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-t2.1"
T2_JOB_FILE="${SUITE_RUN_DIR}/log/job/1/t2/01/job"
exists_ok "${T2_JOB_FILE}"
grep_ok '^CYLC_VACATION_SIGNALS' "${T2_JOB_FILE}"
#-------------------------------------------------------------------------------
purge
exit
