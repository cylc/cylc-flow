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
# Test restart with running task with execution timeout.
. "$(dirname "$0")/test_header"
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" cylc run "${SUITE_NAME}" --no-detach
suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart "${SUITE_NAME}" --no-detach --reference-test
contains_ok "${SUITE_RUN_DIR}/log/job/1/foo/NN/job-activity.log" <<'__LOG__'
[(('event-handler-00', 'execution timeout'), 1) cmd] echo foo.1 'execution timeout'
[(('event-handler-00', 'execution timeout'), 1) ret_code] 0
[(('event-handler-00', 'execution timeout'), 1) out] foo.1 execution timeout
__LOG__
purge_suite "${SUITE_NAME}"
exit
