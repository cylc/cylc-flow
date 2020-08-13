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
# Test restart with a "ready" task. See GitHub #958 (update: and #2610).
. "$(dirname "$0")/test_header"

skip_darwin 'atrun hard to configure on Mac OS'

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}"
SUITE_DIR="${RUN_DIR}/${SUITE_NAME}"
export CYLC_SUITE_LOG_DIR="${SUITE_DIR}/log/suite"
export PATH="${TEST_DIR}/${SUITE_NAME}/bin:$PATH"
LOG="$(find "${CYLC_SUITE_LOG_DIR}/" -type f -name 'log.*' | sort | head -n 1)"
run_ok "${TEST_NAME_BASE}-restart" timeout 1m my-file-poll "${LOG}"
# foo-1 should run when the suite is released
poll_grep_suite_log 'foo-1\.1.*succeeded'
poll_suite_stopped
purge_suite "${SUITE_NAME}"
exit
