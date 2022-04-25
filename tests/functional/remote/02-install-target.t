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
# Test remote installation only happens when appropriate
export REQUIRE_PLATFORM='loc:remote fs:shared comms:?(tcp|ssh)'
. "$(dirname "$0")/test_header"
set_test_number 3

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
#!jinja2
[scheduling]
    [[graph]]
        graph = remote
[runtime]
    [[remote]]
        # this should not require remote-init because the platform
        # has a shared filesystem (same install target)
        script = true
        platform = {{CYLC_TEST_PLATFORM}}
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${WORKFLOW_NAME}" \
    -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
workflow_run_ok "${TEST_NAME_BASE}-run" cylc play --debug \
    --no-detach \
     "${WORKFLOW_NAME}" -s "CYLC_TEST_PLATFORM='${CYLC_TEST_PLATFORM}'"
grep_ok "REMOTE INIT NOT REQUIRED for localhost" "${WORKFLOW_RUN_DIR}/log/scheduler/log"

purge
exit
