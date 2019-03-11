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
. "$(dirname "$0")/test_header"
set_test_number 4

BASE_GLOBALRC="
[cylc]
    health check interval = PT5S
    [[events]]
        abort on inactivity = True
        abort on timeout = True
        inactivity = PT2M
        timeout = PT2M
"
#-------------------------------------------------------------------------------
# test the force shutdown option (auto stop, no restart) in condemned hosts
init_suite "${TEST_NAME_BASE}" <<< '
[scheduling]
    [[dependencies]]
        graph = foo
'

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = localhost
"

cylc run "${SUITE_NAME}" --hold
poll ! test -f "${SUITE_RUN_DIR}/.service/contact"
sleep 1

create_test_globalrc '' "
${BASE_GLOBALRC}
[suite servers]
    run hosts = localhost
    condemned hosts = $(hostname)!
"

FILE=$(cylc cat-log "${SUITE_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME_BASE}-no-auto-restart" "${FILE}" 20 1 \
    'The Cylc suite host will soon become un-available' \
    'This suite will be shutdown as the suite host is' \
    'When another suite host becomes available the suite can' \
    'Suite shutting down - REQUEST(NOW)'

cylc stop "${SUITE_NAME}" --kill 2>/dev/null # in-case test fails
poll test -f "${SUITE_RUN_DIR}/.service/contact"
sleep 1
purge_suite "${SUITE_NAME}"
