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

#------------------------------------------------------------------------------
# Test "cylc message" with multi-line messages. The RE to strip 'at <TIME>' off
# task messages was assuming a single line string.

. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"

LOG="${SUITE_RUN_DIR}/log/job/1/foo/01/job-activity.log"
sed -n '/event-handler-00/,$p' "${LOG}" >'edited-job-activity.log'

cmp_ok 'edited-job-activity.log' - <<__LOG__
[(('event-handler-00', 'custom-1'), 1) cmd]
echo 'the quick brown fox
jumped over the lazy dog'
[(('event-handler-00', 'custom-1'), 1) ret_code] 0
[(('event-handler-00', 'custom-1'), 1) out]
the quick brown fox
jumped over the lazy dog
__LOG__

purge_suite "${SUITE_NAME}"
