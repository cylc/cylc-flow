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

# Test that presence of queued tasks does not cause dependency matching etc. in
# the absence of other activity - GitHub #1787. WARNING: this test is sensitive
# to the number of times the task pool gets processed as the suite runs, in
# response to task state changes.  It will need to be updated if that number
# changes in the future.

. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" cylc run --debug --no-detach "${SUITE_NAME}"

SUITE_LOG_DIR="$RUN_DIR/${SUITE_NAME}/log/suite"
count_ok "BEGIN TASK PROCESSING" "${SUITE_LOG_DIR}/log" 6

purge_suite "${SUITE_NAME}"
exit
