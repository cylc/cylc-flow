#!/usr/bin/env bash
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
export REQUIRE_PLATFORM='loc:remote fs:shared'
. "$(dirname "$0")/test_header"
# shellcheck disable=SC2153
export CYLC_TEST_HOST_2="${CYLC_TEST_HOST}"
export CYLC_TEST_HOST_1="${HOSTNAME}"
#-------------------------------------------------------------------------------
BASE_GLOBAL_CONFIG='
[scheduler]
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
[scheduler]
    [[events]]
[scheduling]
    initial cycle point = 2000
    [[graph]]
        P1Y = foo[-P1Y] => foo
'

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = ${CYLC_TEST_HOST_1}
"

set_test_number 7
#-------------------------------------------------------------------------------
# run suite
cylc run "${SUITE_NAME}" --abort-if-any-task-fails
poll_suite_running
sleep 1
FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)

# condemn the host, the suite will schedule restart in PT60S
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    auto restart delay = -PT60S  # results in +PT60S delay
    [[run hosts]]
        available = ${CYLC_TEST_HOST_1}, ${CYLC_TEST_HOST_2}
        condemned = ${CYLC_TEST_HOST_1}
"
log_scan "${TEST_NAME_BASE}-stop" "${FILE}" 40 1 \
    'The Cylc suite host will soon become un-available' \
    'Suite will restart in 60s'

# condemn the host in "Force Mode", this should cancel the scheduled restart
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        condemned hosts = ${CYLC_TEST_HOST_1}!
"
log_scan "${TEST_NAME_BASE}-stop" "${FILE}" 40 1 \
    'This suite will be shutdown as the suite host is' \
    'When another suite host becomes available the suite can' \
    'Scheduled automatic restart canceled' \
    'Suite shutting down - REQUEST(NOW)' \
    'DONE'

cylc stop --now --now--max-polls=20 --interval=2 "${SUITE_NAME}" 2>'/dev/null'
purge

exit
