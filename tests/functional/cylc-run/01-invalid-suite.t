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
# Test that ``cylc-run`` does not create directories for invalid/not existent
# suites. See https://github.com/cylc/cylc-flow/issues/3097 for more.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
INVALID_SUITE_NAME="broken-parachute-8877-mp5"
run_fail "${TEST_NAME_BASE}-run" cylc run "${INVALID_SUITE_NAME}"
grep_ok "suite service directory not found at" "${TEST_NAME_BASE}-run.stderr"
exists_fail "${HOME}/cylc-run/${INVALID_SUITE_NAME}"

exit
