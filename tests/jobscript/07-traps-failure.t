#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2015 NIWA
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
# Test that trap signals are correctly output for at, background, pbs, etc.
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 13
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
for batch_sys in at background loadleveler pbs sge; do
    TEST_NAME="${TEST_NAME_BASE}-script-$batch_sys"
    run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" "foo_$batch_sys.1"
    grep_ok "^FAIL_SIGNALS='EXIT ERR TERM XCPU'" "${TEST_NAME}.stdout"
done
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-script-slurm"
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" foo_slurm.1
grep_ok "^FAIL_SIGNALS='EXIT ERR XCPU'" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
