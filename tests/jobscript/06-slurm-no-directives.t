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
# Test that directives are written correctly when no extra ones are supplied.
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 5
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-script"
TASK_LOG_PATH="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}/log/job/1/foo/01"
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" foo.1
grep_ok "^#SBATCH --job-name=${SUITE_NAME}.foo.1" "${TEST_NAME}.stdout"
grep_ok "^#SBATCH --output=${TASK_LOG_PATH}/job.out" "${TEST_NAME}.stdout"
grep_ok "^#SBATCH --error=${TASK_LOG_PATH}/job.err" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
