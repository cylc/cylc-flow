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

# Test custom severity event handling.
. "$(dirname "$0")/test_header"
set_test_number 6
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --debug --no-detach --reference-test "${SUITE_NAME}"
FOO_ACTIVITY_LOG="${SUITE_RUN_DIR}/log/job/1/foo/NN/job-activity.log"
SUITE_LOG="${SUITE_RUN_DIR}/log/suite/log"
grep_ok \
"\[(('event-handler-00', 'custom-1'), 1) out\] !!CUSTOM!! foo.1 fugu Data ready for barring" \
    "${FOO_ACTIVITY_LOG}"
grep_ok "\[foo.1\].*Data ready for barring" "${SUITE_LOG}"
grep_ok "\[foo.1\].*Data ready for bazzing" "${SUITE_LOG}"
grep_ok "\[foo.1\].*Aren't the hydrangeas nice?" "${SUITE_LOG}"
purge_suite "${SUITE_NAME}"
