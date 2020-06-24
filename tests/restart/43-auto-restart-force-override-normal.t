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
# Check that "Force Mode" can override a scheduler "Normal Mode" restart.
. "$(dirname "$0")/test_header"
require_remote_platform_wsfs
export CYLC_TEST_HOST_2="${CYLC_TEST_HOST_WSFS}"
export CYLC_TEST_HOST_1="${HOSTNAME}"

BASE_GLOBALRC='
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
'

TEST_DIR="$HOME/cylc-run/" init_suite "${TEST_NAME_BASE}" <<< '
[cylc]
    [[events]]
        abort if any task fails = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        P1Y = foo[-P1Y] => foo
'

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = ${CYLC_TEST_HOST_1}
"

set_test_number 7
#-------------------------------------------------------------------------------
# run suite
cylc run "${SUITE_NAME}"
poll_suite_running
sleep 1
FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)

# condemn the host, the suite will schedule restart in PT60S
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = ${CYLC_TEST_HOST_1}, ${CYLC_TEST_HOST_2}
    condemned hosts = ${CYLC_TEST_HOST_1}
    auto restart delay = -PT60S  # results in +PT60S delay
"
log_scan "${TEST_NAME_BASE}-stop" "${FILE}" 40 1 \
    'The Cylc suite host will soon become un-available' \
    'Suite will restart in 60s'

# condemn the host in "Force Mode", this should cancel the scheduled restart
create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    condemned hosts = ${CYLC_TEST_HOST_1}!
"
log_scan "${TEST_NAME_BASE}-stop" "${FILE}" 40 1 \
    'This suite will be shutdown as the suite host is' \
    'When another suite host becomes available the suite can' \
    'Scheduled automatic restart canceled' \
    'Suite shutting down - REQUEST(NOW)' \
    'DONE'

cylc stop --now --now--max-polls=20 --interval=2 "${SUITE_NAME}" 2>'/dev/null'
purge_suite "${SUITE_NAME}"
purge_suite_platform "${CYLC_REMOTE_PLATFORM_WSFS}" "${SUITE_NAME}"

exit
