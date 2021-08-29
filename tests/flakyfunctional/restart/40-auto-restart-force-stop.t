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
set_test_number 4

BASE_GLOBAL_CONFIG="
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT5S
    [[events]]
        abort on inactivity = True
        abort on stalled timeout = True
        inactivity = PT2M
        stalled timeout = PT2M
"
#-------------------------------------------------------------------------------
# test the force shutdown option (auto stop, no restart) in condemned hosts
init_workflow "${TEST_NAME_BASE}" <<< '
[scheduler]
    allow implicit tasks = True
[scheduling]
    [[graph]]
        R1 = foo
'

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = localhost
"

cylc play "${WORKFLOW_NAME}" --pause
poll_workflow_running

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        available = localhost
        condemned = $(localhost_fqdn)!
"

FILE=$(cylc cat-log "${WORKFLOW_NAME}" -m p |xargs readlink -f)
log_scan "${TEST_NAME_BASE}-no-auto-restart" "${FILE}" 20 1 \
    'The Cylc workflow host will soon become un-available' \
    'This workflow will be shutdown as the workflow host is' \
    'When another workflow host becomes available the workflow can' \
    'Workflow shutting down - REQUEST(NOW)'

cylc stop --kill --max-polls=10 --interval=2 "${WORKFLOW_NAME}" 2>'/dev/null'
purge
exit
