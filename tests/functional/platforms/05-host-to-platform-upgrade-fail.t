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
# Check that platform upgraders fail if no platform can be found which
# matches host settings.


export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 3

create_test_global_config '' "
[platforms]
  [[wibble]]
    hosts = ${CYLC_TEST_HOST}
    retrieve job logs = True
"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"


# Both of these cases should validate ok.
run_ok "${TEST_NAME_BASE}-validate" \
  cylc validate "${SUITE_NAME}" \
     -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}"

# Check that the cfgspec/suite.py has issued a warning about upgrades.
grep_ok "\[not_upgradable_cylc7_settings\]\[remote\]host = parasite"\
  "${TEST_NAME_BASE}-validate.stderr"

# Run the suite
suite_run_fail "${TEST_NAME_BASE}-run" \
  cylc run --debug --no-detach \
  -s "CYLC_TEST_HOST=${CYLC_TEST_HOST}" "${SUITE_NAME}"

purge_suite_platform "${CYLC_TEST_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
