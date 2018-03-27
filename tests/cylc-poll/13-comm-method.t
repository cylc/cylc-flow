#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
# Test poll intervals is used from both global.rc and suite.rc
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
create_test_globalrc '
[hosts]
   [[localhost]]
        task communication method = poll
        execution polling intervals = 10*PT6S
        submission polling intervals = 10*PT6S'

suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}"
LOG_FILE="${SUITE_RUN_DIR}/log/suite/log"
run_ok "log" grep -Fq '[t1.1] -next job poll' "${LOG_FILE}"
run_ok "log" grep -Fq '[t2.1] -next job poll' "${LOG_FILE}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
