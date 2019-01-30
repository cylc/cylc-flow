#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test restart with a "ready" task. See GitHub #958 (update: and #2610).
. "$(dirname "$0")/test_header"

set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
SUITE_DIR="$(cylc get-global-config --print-run-dir)/${SUITE_NAME}"
export CYLC_SUITE_LOG_DIR="${SUITE_DIR}/log/suite"
export PATH="${TEST_DIR}/${SUITE_NAME}/bin:$PATH"
LOG_FILES=($(ls ${CYLC_SUITE_LOG_DIR}))
run_ok "${TEST_NAME_BASE}-restart" \
    timeout 1m my-file-poll "${CYLC_SUITE_LOG_DIR}/${LOG_FILES[1]}"
# foo-1 should run when the suite is released
run_ok "${TEST_NAME_BASE}-foo-1" \
    timeout 1m my-log-grepper 'foo-1\.1.*succeeded'
timeout 1m my-log-grepper 'Suite shutting down'
purge_suite "${SUITE_NAME}"
exit
