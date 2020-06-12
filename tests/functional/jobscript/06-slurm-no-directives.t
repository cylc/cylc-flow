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
grep_ok "^#SBATCH --job-name=foo.1.${SUITE_NAME}" "${TEST_NAME}.stdout"
grep_ok "^#SBATCH --output=${TASK_LOG_PATH}/job.out" "${TEST_NAME}.stdout"
grep_ok "^#SBATCH --error=${TASK_LOG_PATH}/job.err" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
