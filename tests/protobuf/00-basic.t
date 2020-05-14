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
set_test_number 1
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    UTC mode = True
    [[events]]
        abort if any task fails = True
        abort on timeout = True
        timeout=PT1M
[scheduling]
    cycling mode = integer
    initial cycle point = 1
    [[dependencies]]
        graph = foo
[runtime]
    [[foo]]
        script = """
            sleep 10
        """
__SUITERC__
cylc run "${SUITE_NAME}"
poll_suite_running
run_ok "${TEST_NAME_BASE}" python3 -c "
from cylc.flow.network.client import SuiteRuntimeClient
from cylc.flow.network.server import PB_METHOD_MAP
client = SuiteRuntimeClient('${SUITE_NAME}')
pb_msg = client.serial_request('pb_entire_workflow')
pb_data = PB_METHOD_MAP['pb_entire_workflow']()
pb_data.ParseFromString(pb_msg)
if pb_data.workflow.id != '${USER}|${SUITE_NAME}':
    raise ValueError(f'incorrect flow id: {pb_data.workflow.id}')
"
cylc stop --now --now "${SUITE_NAME}"
poll_suite_stopped
purge_suite "${SUITE_NAME}"
exit
