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
# Test #958: task in ready state, stop now, restart hold, release
. "$(dirname "$0")/test_header"

set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
SUITE_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
export CYLC_SUITE_LOG_DIR="${SUITE_DIR}/log/suite"
export PATH="${TEST_DIR}/${SUITE_NAME}/bin:$PATH"
run_ok "${TEST_NAME_BASE}-restart" \
    timeout 1m my-file-poll "${CYLC_SUITE_LOG_DIR}/log.1"
# foo-1 should run when the suite is released
run_ok "${TEST_NAME_BASE}-foo-1" \
    timeout 1m my-log-grepper 'foo-1.1 succeeded'
timeout 1m my-log-grepper 'Suite shutting down'
purge_suite "${TEST_NAME_BASE}"
exit
