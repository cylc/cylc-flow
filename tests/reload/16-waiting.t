#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test reload a waiting task does not cause DB integrity error. cylc/cylc#1221
. $(dirname $0)/test_header
set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --reference-test "${SUITE_NAME}"
run_fail "${TEST_NAME_BASE}-database-integrity-error" \
   grep -q 'Database Integrity Error' "${TEST_NAME}.stderr"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
