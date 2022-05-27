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
# Platforms can have default directives and these are overridden as expected.
export REQUIRE_PLATFORM="runner:slurm"
. "$(dirname "$0")/test_header"

set_test_number 5

create_test_global_config "" "
    [platforms]
        [[no_default, default_only, overridden, neither]]
            hosts = localhost
            job runner = slurm
        [[default_only, overridden]]
            [[[directives]]]
                --wurble=foo
"

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONF__'
[scheduler]
    [[events]]
        stall timeout = PT0S
[scheduling]
    [[graph]]
        R1 = lewis & morse & barnaby & cadfael

[runtime]
    [[lewis]]
        platform = no_default
        [[[directives]]]
            --wurble=bar
    [[morse]]
        platform = default_only
    [[barnaby]]
        platform = overridden
        [[[directives]]]
            --wurble=qux
    [[cadfael]]
        platform = neither

__FLOW_CONF__

run_fail "${TEST_NAME_BASE}-play" \
    cylc play "${WORKFLOW_NAME}" --no-detach

LOG_DIR="${RUN_DIR}/${WORKFLOW_NAME}/log/job/1/"

named_grep_ok "${TEST_NAME_BASE}-no-default" "--wurble=bar" "${LOG_DIR}/lewis/NN/job"
named_grep_ok "${TEST_NAME_BASE}-default-only" "--wurble=foo" "${LOG_DIR}/morse/NN/job"
named_grep_ok "${TEST_NAME_BASE}-overridden" "--wurble=qux" "${LOG_DIR}/barnaby/NN/job"
grep_fail "--wurble" "${LOG_DIR}/cadfael/NN/job"

purge
exit 0

