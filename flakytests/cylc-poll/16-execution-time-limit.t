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
# Test execution time limit polling.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 4
create_test_globalrc '
[job platforms]
   [[localhost]]
        task communication method = poll
        submission polling intervals = PT2S
        execution polling intervals = PT1M
        batch system = background
        execution time limit polling intervals = PT5S
'
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
cmp_times () {
    # Test if the times $1 and $2 are within $3 seconds of each other.
    python3 -u - "$@" <<'__PYTHON__'
import sys
from metomi.isodatetime.parsers import TimePointParser
parser = TimePointParser()
time_1 = parser.parse(sys.argv[1])
time_2 = parser.parse(sys.argv[2])
if abs((time_1 - time_2).get_seconds()) > int(sys.argv[3]):
    sys.exit("abs(predicted - actual) > tolerance: %s" % sys.argv[1:])
__PYTHON__
}
time_offset () {
    # Add an ISO8601 duration to an ISO8601 date-time.
    python3 -u - "$@" <<'__PYTHON__'
import sys
from metomi.isodatetime.parsers import TimePointParser, DurationParser
print(
    TimePointParser().parse(sys.argv[1]) + DurationParser().parse(sys.argv[2]))
__PYTHON__
}
#-------------------------------------------------------------------------------
LOG="${SUITE_RUN_DIR}/log/suite/log"
# Test logging of the "next job poll" message when task starts.
TEST_NAME="${TEST_NAME_BASE}-log-entry"
LINE="$(grep -F '[foo.1] -health check settings: execution timeout=PT10S' "${LOG}")"
run_ok "${TEST_NAME}" grep -q 'health check settings: execution timeout=PT10S' \
    <<< "${LINE}"
# Determine poll times.
PREDICTED_POLL_TIME=$(time_offset \
    "$(cut -d ' ' -f 1 <<< "${LINE}")" \
    "$(sed -n 's/^.*execution timeout=\([^,]\+\).*$/\1/p' <<< "${LINE}")")
ACTUAL_POLL_TIME=$(sed -n \
    's/\(.*\) INFO - \[foo.1\] status=running: (polled)failed .*/\1/p' \
    "${LOG}")
# Test execution timeout polling.
# Main loop is roughly 1 second, but integer rounding may give an apparent 2
# seconds delay, so set threshold as 2 seconds.
run_ok "${TEST_NAME_BASE}-poll-time" \
    cmp_times "${PREDICTED_POLL_TIME}" "${ACTUAL_POLL_TIME}" '10'
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
