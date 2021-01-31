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
export REQUIRE_PLATFORM='loc:remote fs:shared'
. "$(dirname "$0")/test_header"
set_test_number 10
#-------------------------------------------------------------------------------
# test the failure recovery mechanism
BASE_GLOBAL_CONFIG="
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT15S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
[scheduler]
    [[run hosts]]
        available = localhost, ${CYLC_TEST_HOST}"

TEST_NAME="${TEST_NAME_BASE}"
init_suite "${TEST_NAME}" <<< '
[scheduling]
    [[graph]]
        R1 = foo
'
create_test_global_config '' "${BASE_GLOBAL_CONFIG}"
run_ok "${TEST_NAME}-suite-start" \
    cylc run "${SUITE_NAME}" --host=localhost --hold
poll_suite_running

# corrupt suite
rm "${SUITE_RUN_DIR}/flow.cylc"

# condemn localhost
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        condemned = $(hostname)
"

FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME}-shutdown" "${FILE}" 20 1 \
    'The Cylc suite host will soon become un-available' \
    'Suite shutting down - REQUEST(NOW-NOW)' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    'Could not restart suite will retry in 5s' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    'Could not restart suite will retry in 5s' \
    "Attempting to restart on \"${CYLC_TEST_HOST}\"" \
    'Could not restart suite will retry in 5s' \
    'Suite unable to automatically restart after 3 tries'

# stop suite - suite should already by stopped but just to be safe
cylc stop --max-polls=10 --interval=2 -kill "${SUITE_NAME}" 2>'/dev/null'
purge

exit
