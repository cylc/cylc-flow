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
# Test bad job submission, activity log has original command and some stderr
# with the host name written.
export REQUIRE_PLATFORM='runner:at loc:remote'
. "$(dirname "$0")/test_header"
set_test_number 2

create_test_global_config '' "
[platforms]
    [[${CYLC_TEST_PLATFORM}]]
        job runner = at
        job runner command template = at non
"

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" \
       -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" \
       -s "CYLC_TEST_HOST='${CYLC_TEST_HOST}'"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test \
    -s "CYLC_TEST_HOST='${CYLC_TEST_HOST}'" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'" "${SUITE_NAME}"

purge
exit
