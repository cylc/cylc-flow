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
. "$(dirname "$0")/test_header"
set_test_number 3

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
# test that workflows will not attempt to auto stop-restart if there is no
# available host to restart on
init_workflow "${TEST_NAME_BASE}" <<< '
[scheduler]
    UTC mode = True
    allow implicit tasks = True
[scheduling]
    initial cycle point = 2000
    [[graph]]
        P1D = foo
'

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = localhost
"

cylc play "${WORKFLOW_NAME}" --debug
poll_workflow_running

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = localhost
        condemned = $(localhost_fqdn)
"

FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME_BASE}-no-auto-restart" "${FILE}" 20 1 \
    'The Cylc workflow host will soon become un-available' \
    'Workflow cannot automatically restart: No alternative host' \
    'Workflow cannot automatically restart: No alternative host' \

cylc stop --kill --max-polls=10 --interval=2 "${WORKFLOW_NAME}"
purge
exit
