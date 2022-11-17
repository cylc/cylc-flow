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
#------------------------------------------------------------------------------

# Test persistence of xtrigger results across restart. A cycling task depends
# on a non cycle-point dependent custom xtrigger called "faker". In the first
# cycle point the xtrigger succeeds and returns a result, then a task shuts
# the workflow down.  Then we replace the custom xtrigger function with one that
# will fail if called again - which should not happen because the original
# result should be remembered (as this xtrigger is not cycle point dependent).
# Also test the correct result is broadcast to the dependent task before and
# after workflow restart.

. "$(dirname "$0")/test_header"
set_test_number 6

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Install the succeeding xtrigger function.
cd "${WORKFLOW_RUN_DIR}" || exit 1
mkdir -p 'lib/python'
cp "${WORKFLOW_RUN_DIR}/faker_succ.py" 'lib/python/faker.py'

# Validate the test workflow.
run_ok "${TEST_NAME_BASE}-val" cylc validate --debug "${WORKFLOW_NAME}"

# Run the first cycle, till auto shutdown by task.
TEST_NAME="${TEST_NAME_BASE}-run"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach --debug "${WORKFLOW_NAME}"

# Check the broadcast result of xtrigger.
cylc cat-log "${WORKFLOW_NAME}//2010/foo" >'2010.foo.out'
grep_ok 'NAME is bob' '2010.foo.out'

# Replace the xtrigger function with one that will fail if called again.
cp "${WORKFLOW_RUN_DIR}/faker_fail.py" 'lib/python/faker.py'

# Validate again (with the new xtrigger function).
run_ok "${TEST_NAME_BASE}-val2" cylc validate --debug "${WORKFLOW_NAME}"

# Restart the workflow, to run the final cycle point.
TEST_NAME="${TEST_NAME_BASE}-restart"
workflow_run_ok "${TEST_NAME}" cylc play --no-detach "${WORKFLOW_NAME}"

# Check the broadcast result has persisted from first run.
cylc cat-log "${WORKFLOW_NAME}//2011/foo" >'2011.foo.out'
grep_ok 'NAME is bob' '2011.foo.out'

purge
