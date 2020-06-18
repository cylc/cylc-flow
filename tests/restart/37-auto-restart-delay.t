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
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
CYLC_TEST_HOST="$( \
    cylc get-global-config -i '[test battery]remote platform with shared fs' \
    2>'/dev/null')"
if [[ -z "${CYLC_TEST_HOST}" ]]; then
    skip_all '"[test battery]remote platform with shared fs": not defined'
fi
export CYLC_TEST_HOST
set_test_number 6
time_gt () {
    python3 -c "
import sys
from metomi.isodatetime.parsers import TimePointParser
parser = TimePointParser()
sys.exit(not parser.parse('$1') > parser.parse('$2'))
"
}
BASE_GLOBALRC="
[cylc]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT5S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
"
#-------------------------------------------------------------------------------
# Test the delayed restart feature
TEST_DIR="$HOME/cylc-run/" init_suite "${TEST_NAME_BASE}" <<< '
[cylc]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        P1D = foo
'

MAX_RESTART_DELAY=30
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = localhost
    auto restart delay = PT${MAX_RESTART_DELAY}S
"

# Run suite.
cylc run "${SUITE_NAME}" --hold
poll_suite_running

# Condemn host - trigger stop-restart.
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = ${CYLC_TEST_HOST}
    condemned hosts = $(hostname)
    auto restart delay = PT20S
"

# Check stop-restart working.
FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME_BASE}-auto-restart" "${FILE}" 60 1 \
    'The Cylc suite host will soon become un-available' \
    'Suite will restart in' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    "Suite now running on \"${CYLC_TEST_HOST}\""

# Extract scheduled restart time from the log.
TIMES=$(grep --color=never 'Suite will restart in' "${FILE}" | \
    sed 's/.*will restart in \(.*\)s (at \(.*\))/\1|\2/')
RESTART_DELAY=$(cut -d '|' -f 1 <<< "${TIMES}")
RESTART_SCHEDULED_TIME=$(cut -d '|' -f 2 <<< "${TIMES}")

# Extract actual restart time from the log.
RESTART_TIME=$(grep --color=never 'Attempting to restart' "${FILE}" | \
    sed 's/\(.*\) INFO.*Attempting to restart.*/\1/')

# Check the restart delay is correct.
TEST_NAME="${TEST_NAME_BASE}-restart-delay"
if [[ "${RESTART_DELAY}" -lt "${MAX_RESTART_DELAY}" && "${RESTART_DELAY}" -gt 0 ]]
then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

# Check the actual restart time is after the scheduled restart time.
TEST_NAME="${TEST_NAME_BASE}-restart-time"
if time_gt "${RESTART_TIME}" "${RESTART_SCHEDULED_TIME}"; then
    ok "${TEST_NAME}"
else
    fail "${TEST_NAME}"
fi

cylc stop "${SUITE_NAME}" --now --now 2>/dev/null
sleep 1
purge_suite "${SUITE_NAME}"

exit
