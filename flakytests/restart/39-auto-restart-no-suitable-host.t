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
set_test_number 5

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
# test that suites will not attempt to auto stop-restart if there is no
# available host to restart on
init_suite "${TEST_NAME_BASE}" <<< '
[cylc]
    UTC mode = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        P1D = foo
'

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = localhost
"

cylc run "${SUITE_NAME}" --debug
poll_suite_running

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = localhost
    condemned hosts = $(get_fqdn_by_host)
"

FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME_BASE}-no-auto-restart" "${FILE}" 20 1 \
    'The Cylc suite host will soon become un-available' \
    'Suite cannot automatically restart because:' \
    'No alternative host to restart suite on.' \
    'Suite cannot automatically restart because:' \
    'No alternative host to restart suite on.'

cylc stop --kill --max-polls=10 --interval=2 "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
