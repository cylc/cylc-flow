#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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
export REQUIRE_PLATFORM='loc:remote fs:shared runner:background'
. "$(dirname "$0")/test_header"
set_test_number 6
#-------------------------------------------------------------------------------
time_gt () {
    python3 -c "
import sys
from metomi.isodatetime.parsers import TimePointParser
parser = TimePointParser()
sys.exit(not parser.parse('$1') > parser.parse('$2'))
"
}
BASE_GLOBAL_CONFIG="
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT5S
    [[events]]
        abort on inactivity timeout = True
        abort on stall timeout = True
        inactivity timeout = PT2M
        stall timeout = PT2M
"
#-------------------------------------------------------------------------------
# Test the delayed restart feature
init_workflow "${TEST_NAME_BASE}" <<< '
[scheduler]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        P1D = foo
[runtime]
    [[foo]]
'

MAX_RESTART_DELAY=30
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    auto restart delay = PT${MAX_RESTART_DELAY}S
    [[run hosts]]
        available = localhost
"

# Run workflow.
cylc play "${WORKFLOW_NAME}" --pause
poll_workflow_running

# Condemn host - trigger stop-restart.
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    auto restart delay = PT20S
    [[run hosts]]
        available = ${CYLC_TEST_HOST}
        condemned = $(hostname)
"

# Check stop-restart working.
FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME_BASE}-auto-restart" "${FILE}" 60 1 \
    'The Cylc workflow host will soon become un-available' \
    'Workflow will restart in' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    "Workflow now running on \"${CYLC_TEST_HOST}\""

# Extract scheduled restart time from the log.
TIMES=$(grep --color=never 'Workflow will restart in' "${FILE}" | \
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

cylc stop "${WORKFLOW_NAME}" --now --now 2>/dev/null

purge
