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
# Check that platform upgraders work sensibly.
# The following scenarios should be covered:
#   - Task with no settings
#   - Task with a host setting that should match the test platform
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
set_test_number 6

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Ensure that a mix of syntax will fail.
run_fail "${TEST_NAME_BASE}-validate-fail" \
    cylc validate "flow2.cylc"

# Ensure that you can validate workflow
run_ok "${TEST_NAME_BASE}-run" \
    cylc validate "${WORKFLOW_NAME}" \
        -s "CYLC_TEST_HOST='${CYLC_TEST_HOST}'" \
        -s CYLC_TEST_HOST_FQDN="'$(ssh "$CYLC_TEST_HOST" hostname -f)'"

# Check that the cfgspec/workflow.py has issued a warning about upgrades.
grep_ok "\[t1\]\[remote\]host = ${CYLC_TEST_HOST}"\
    "${TEST_NAME_BASE}-run.stderr"

# the namespace with the host setting will be logged not the task that
# inherits from it (because it happens in the cfgspec not the config)
grep_ok "\[T2\]\[remote\]host = ${CYLC_TEST_HOST}"\
    "${TEST_NAME_BASE}-run.stderr"

# Run the workflow
echo $CYLC_TEST_HOST >&2
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --reference-test \
    -s CYLC_TEST_HOST="'$CYLC_TEST_HOST'" \
    -s CYLC_TEST_HOST_FQDN="'$(ssh "$CYLC_TEST_HOST" hostname -f)'" \
    "${WORKFLOW_NAME}"

grep "host=" "${WORKFLOW_RUN_DIR}/log/scheduler/log" > hosts.log

grep_ok "\[2/t2.*\].*host=${CYLC_TEST_HOST}" hosts.log

purge
exit
