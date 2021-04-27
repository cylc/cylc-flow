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
# Checks ZMQ keys are created and deleted on shutdown - local.
. "$(dirname "$0")/test_header"
set_test_number 10
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    cycle point format = %Y
    allow implicit tasks = True
[scheduling]
    initial cycle point = 2020
    [[graph]]
        R1 = t1
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}"

SRVD="${WORKFLOW_RUN_DIR}/.service"

workflow_run_ok "${TEST_NAME_BASE}-run-pause" cylc play --pause "${WORKFLOW_NAME}"

exists_ok "${SRVD}/client.key_secret"
exists_ok "${SRVD}/server.key_secret"
exists_ok "${SRVD}/server.key"
exists_ok "${SRVD}/client_public_keys/client_localhost.key"

cylc stop --max-polls=60 --interval=1 "${WORKFLOW_NAME}"
exists_fail "${SRVD}/client.key_secret"
exists_fail "${SRVD}/server.key_secret"
exists_fail "${SRVD}/server.key"
exists_fail "${SRVD}/client_public_keys/client_localhost.key"

purge
exit
