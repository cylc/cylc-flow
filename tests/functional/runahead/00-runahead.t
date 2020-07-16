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
# Test runahead limit is being enforced
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" runahead
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
run_fail "${TEST_NAME}" cylc run --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-check-fail"
DB="${SUITE_RUN_DIR}/log/db"
TASKS="$(sqlite3 "${DB}" 'select count(*) from task_states where status=="failed"')"
run_ok "${TEST_NAME_BASE}-check-fail" test "${TASKS}" -eq 4
#-------------------------------------------------------------------------------
grep_ok 'suite timed out after' "${SUITE_RUN_DIR}/log/suite/log"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
