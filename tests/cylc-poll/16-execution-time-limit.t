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
# Test execution time limit polling.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 3

ETL=5  # execution time limit -> seconds
ETL_P_INT=7  # execution time limit polling intervals -> seconds

create_test_globalrc "
[hosts]
   [[localhost]]
        execution polling intervals = PT1M
        [[[batch systems]]]
            [[[[background]]]]
                execution time limit polling intervals = PT${ETL_P_INT}S"
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" -s "ETL=$ETL"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --no-detach "${SUITE_NAME}" -s "ETL=$ETL"
#-------------------------------------------------------------------------------
cmp_times () {
    # Test if the times $1 and $2 are within $3 seconds of each other.
    python3 -u - "$@" <<'__PYTHON__'
import sys
from isodatetime.parsers import TimePointParser
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
from isodatetime.parsers import TimePointParser, DurationParser
print(
    TimePointParser().parse(sys.argv[1]) + DurationParser().parse(sys.argv[2]))
__PYTHON__
}
#-------------------------------------------------------------------------------
LOG="${SUITE_RUN_DIR}/log/suite/log"
SUBMITTED_TIME="$(sed -n \
    's/\(.*\) \w.*\[foo.1\] status=submitted: (received)started.*/\1/p' \
    "${LOG}" | head -n 1)"
PREDICTED_POLL_TIME=$(time_offset \
    "${SUBMITTED_TIME}" \
    "PT$(( ETL + ETL_P_INT ))S" )
ACTUAL_POLL_TIME=$(sed -n \
    's/\(.*\) \w.*\[foo.1\] status=running: (polled)failed.*/\1/p' "${LOG}" \
    | head -n 1)

# Test execution timeout polling.
# Main loop is roughly 1 second, but integer rounding may give an apparent 2
# seconds delay, so set threshold as 2 seconds.
run_ok "${TEST_NAME_BASE}-poll-time" \
    cmp_times "${PREDICTED_POLL_TIME}" "${ACTUAL_POLL_TIME}" '2'
if [[ $FAILURES -gt 0 ]]; then
    cylc cat-log "${SUITE_NAME}" >&2
    echo >&2
    echo "SUBM_TIME: $SUBMITTED_TIME" >&2
    echo "PRED_TIME: $PREDICTED_POLL_TIME" >&2
    echo "POLL_TIME: $ACTUAL_POLL_TIME" >&2
fi
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
