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
# Check that platform upgraders work sensibly.
# The following scenarios should be covered:
#   - Task with no settings
#   - Task with a host setting that should match platform "wibble"
export REQUIRE_PLATFORM='loc:remote'
. "$(dirname "$0")/test_header"
set_test_number 5

create_test_global_config '' "
[platforms]
  [[wibble]]
    hosts = ${CYLC_TEST_HOST}
    install target = ${CYLC_TEST_HOST}
    retrieve job logs = True
"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

# Ensure that a mix of syntax will fail.
run_fail "${TEST_NAME_BASE}-validate-fail" \
  cylc validate "flow2.cylc"

# Ensure that you can validate suite
run_ok "${TEST_NAME_BASE}-validate" \
  cylc validate "${SUITE_NAME}" \
     -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}"

# Check that the cfgspec/suite.py has issued a warning about upgrades.
grep_ok "\[upgradeable_cylc7_settings\]\[remote\]host = ${CYLC_TEST_HOST}"\
  "${TEST_NAME_BASE}-validate.stderr"

# Run the suite
suite_run_ok "${TEST_NAME_BASE}-run" \
  cylc run --debug --no-detach \
  -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}" "${SUITE_NAME}"

# Check that the upgradeable config has been run on a sensible host.
grep_ok \
  "@${CYLC_TEST_HOST}"\
  "${SUITE_RUN_DIR}/log/job/1/upgradeable_cylc7_settings/NN/job.out"

purge_suite_platform "${CYLC_TEST_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
