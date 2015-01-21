#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test that copyable environment variables is written
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
