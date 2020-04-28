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
#------------------------------------------------------------------------------

# Test persistence of xtrigger results across restart. A cycling task depends
# on a non cycle-point dependent custom xtrigger called "faker". In the first
# cycle point the xtrigger succeeds and returns a result, then a task shuts
# the suite down.  Then we replace the custom xtrigger function with one that
# will fail if called again - which should not happen because the original
# result should be remembered (as this xtrigger is not cycle point dependent).
# Also test the correct result is broadcast to the dependent task before and
# after suite restart.

. "$(dirname "$0")/test_header"
set_test_number 6

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the succeeding xtrigger function.
mkdir -p 'lib/python'
cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/faker_succ.py" 'lib/python/faker.py'

# Validate the test suite.
run_ok "${TEST_NAME_BASE}-val" cylc val --debug "${SUITE_NAME}"

# Run the first cycle, till auto shutdown by task.
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --no-detach --debug "${SUITE_NAME}"

# Check the broadcast result of xtrigger.
cylc cat-log "${SUITE_NAME}" 'foo.2010' >'foo.2010.out'
grep_ok 'NAME is bob' 'foo.2010.out'

# Replace the xtrigger function with one that will fail if called again.
cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/faker_fail.py" 'lib/python/faker.py'

# Validate again (with the new xtrigger function).
run_ok "${TEST_NAME_BASE}-val2" cylc val --debug "${SUITE_NAME}"

# Restart the suite, to run the final cycle point.
TEST_NAME="${TEST_NAME_BASE}-restart"
suite_run_ok "${TEST_NAME}" cylc restart --no-detach "${SUITE_NAME}"

# Check the broadcast result has persisted from first run.
cylc cat-log "${SUITE_NAME}" 'foo.2011' >'foo.2011.out'
grep_ok 'NAME is bob' 'foo.2011.out'

purge_suite "${SUITE_NAME}"
