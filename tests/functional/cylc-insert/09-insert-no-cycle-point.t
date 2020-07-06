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
# Test cylc insert command with no cycle point
. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}" \
    cylc run -v -v --reference-test --no-detach "${SUITE_NAME}"
JOB_LOG_D="$RUN_DIR/${SUITE_NAME}/log/job"
contains_ok "${JOB_LOG_D}/20140101T0000+01/prep/NN/job.err" \
    <<<'UserInputError: "foo": invalid task ID (argument 1)'

purge_suite "${SUITE_NAME}"
exit
