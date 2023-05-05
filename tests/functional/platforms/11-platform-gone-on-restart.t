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
# If a platform is deleted from global config and restart cannot find an
# approproiate match, don't keep going.
# 1. Run a workflow which stops leaving a job running on a platform.
# 2. Delete the platform from global.cylc
# 3. Attempt to restart.
# 4. Check that restart fails in the desired manner.
. "$(dirname "$0")/test_header"

set_test_number 3

create_test_global_config "" "
    [platforms]
        [[myplatform]]
            hosts = localhost
            install target = localhost
"

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONF__'
[scheduling]
    initial cycle point = 2934
    [[graph]]
        R1 = foo => bar

[runtime]
    [[foo]]
        script = """
            cylc stop ${CYLC_WORKFLOW_ID} --now --now
        """
        platform = myplatform
    [[bar]]
        script = true  # only runs on restart
__FLOW_CONF__

run_ok "${TEST_NAME_BASE}-play" \
    cylc play "${WORKFLOW_NAME}" --no-detach

# Wait for workflow to stop, then wreck the global config:
create_test_global_config "" "
"

# Test that restart fails:
run_fail "${TEST_NAME_BASE}-restart" \
    cylc play "${WORKFLOW_NAME}" --no-detach
named_grep_ok \
    "${TEST_NAME_BASE}-cannot-restart" \
    "platforms are not defined in the global.cylc" \
    "${RUN_DIR}/${WORKFLOW_NAME}/log/scheduler/log"

purge
