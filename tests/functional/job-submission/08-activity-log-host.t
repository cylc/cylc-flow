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
# Test job submission, activity log has remote host name
export CYLC_TEST_IS_GENERIC=false
. "$(dirname "$0")/test_header"
require_remote_platform
set_test_number 2

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" \
    cylc validate "${SUITE_NAME}" -s "CYLC_REMOTE_PLATFORM=${CYLC_REMOTE_PLATFORM}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test -s "CYLC_REMOTE_PLATFORM=${CYLC_REMOTE_PLATFORM}" \
    "${SUITE_NAME}"

purge_suite_remote "${CYLC_REMOTE_PLATFORM}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
