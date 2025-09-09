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
export REQUIRE_PLATFORM='loc:remote fs:shared runner:background'
. "$(dirname "$0")/test_header"
set_test_number 3
if ${CYLC_TEST_DEBUG:-false}; then ERR=2; else ERR=1; fi
#-------------------------------------------------------------------------------
# ensure that workflows don't get auto stop-restarted if they are already stopping
BASE_GLOBAL_CONFIG="
[scheduler]
    [[main loop]]
        plugins = health check, auto restart
        [[[auto restart]]]
            interval = PT1S
    [[events]]
        abort on inactivity timeout = True
        abort on stall timeout = True
        inactivity timeout = PT1M
        stall timeout = PT1M
    [[run hosts]]
        available = localhost, ${CYLC_TEST_HOST}"

TEST_NAME="${TEST_NAME_BASE}"

init_workflow "${TEST_NAME}" - <<'__FLOW_CONFIG__'
[scheduling]
    [[graph]]
        R1 = foo => bar
[runtime]
    [[foo]]
        script = cylc stop "${CYLC_WORKFLOW_ID}"; sleep 15
    [[bar]]
__FLOW_CONFIG__

create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
"

run_ok "${TEST_NAME}-workflow-start" cylc play "${WORKFLOW_NAME}" --host=localhost
run_ok "wait-for-task-foo-to-start" \
    cylc workflow-state "${WORKFLOW_NAME}//1/foo:started" --triggers --interval=1 --max-polls=20 >& $ERR

# condemn localhost
create_test_global_config '' "
${BASE_GLOBAL_CONFIG}
[scheduler]
    [[run hosts]]
        condemned = $(hostname)
"

# wait for workflow to die of natural causes
poll_workflow_stopped
grep_ok 'Workflow shutting down - REQUEST(CLEAN)' \
    "$(cylc cat-log "${WORKFLOW_NAME}" -m p)"

purge

exit
