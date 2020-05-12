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
#-------------------------------------------------------------------------------
# Test clean up of port file, on bad start with invalid initial cycle point.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
# N.B. No validate test because this suite does not validate.
TEST_NAME="${TEST_NAME_BASE}-run"
run_fail "${TEST_NAME}" cylc run "${SUITE_NAME}" --debug --no-detach
RUND="$RUN_DIR/${SUITE_NAME}"
exists_fail "${RUND}/.service/contact"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
