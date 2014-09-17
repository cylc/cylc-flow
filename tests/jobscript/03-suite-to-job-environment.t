#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test that suite to job environment is written
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
FOO='foo foo' BAR='bar bar' BAZ='baz baz' CYLC_CONF_PATH="${PWD}/conf" \
    suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}"
SUITE_RUN_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
JOB_FILE="${SUITE_RUN_DIR}/log/job/1/foo/NN/job"
run_ok "${TEST_NAME}.stdout-FOO" grep -q "FOO='foo foo'" "${JOB_FILE}"
run_ok "${TEST_NAME}.stdout-BAR" grep -q "BAR='bar bar'" "${JOB_FILE}"
run_ok "${TEST_NAME}.stdout-BAZ" grep -q "BAZ='baz baz'" "${JOB_FILE}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
