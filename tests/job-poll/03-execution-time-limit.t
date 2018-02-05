#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test  execution time limit polling.
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
create_test_globalrc '
[hosts]
   [[localhost]]
        task communication method = poll
        submission polling intervals = PT2S
        execution polling intervals = PT1M
        [[[batch systems]]]
            [[[[background]]]]
                execution time limit polling intervals = PT5S'
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
cmp_times () {
    # Test if the times $1 and $2 are within $3 seconds of eachother.
    python -c '
import sys
from isodatetime.parsers import TimePointParser
parser = TimePointParser()
time_1 = parser.parse(sys.argv[1])
time_2 = parser.parse(sys.argv[2])
diff = (time_1 - time_2).get_seconds()
if abs(diff) <= int(sys.argv[3]):
    sys.exit(0)
else:
    sys.exit(1)
    ' $1 $2 $3
}
#-------------------------------------------------------------------------------
LOG_FILE="${SUITE_RUN_DIR}/log/suite/log"
# Test logging of the "next job poll" message when task starts.
TEST_NAME="${TEST_NAME_BASE}-log-entry"
LINE=$(grep -A 1 '[foo.1].*current\:submitted.*started' "${LOG_FILE}" | tail -1)
run_ok "${TEST_NAME}" grep 'next job poll in PT10S' <<< "$LINE"
# Test execution timeout polling.
TEST_NAME="${TEST_NAME_BASE}-poll-time"
PREDICTED_POLL_TIME=$(sed 's/.*after \(.*\)).*/\1/' <<< "${LINE}")
ACTUALL_POLL_TIME=$(sed -n \
    's/\(.*\) INFO - \[foo.1\] -(current:running) failed (polled).*/\1/p' \
    "${LOG_FILE}")
if cmp_times ${PREDICTED_POLL_TIME} ${ACTUALL_POLL_TIME} 1; then
    ok "${TEST_NAME}"
else
    echo "Poll time differs from log entry '${PREDICTED_POLL_TIME} != " \
        "${ACTUALL_POLL_TIME}'." >&2
    fail "${TEST_NAME}"
fi
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
