#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

# Test task and family hold via exact and inexact name matches.
. "$(dirname "$0")/test_header"

set_test_number 3

init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    allow implicit tasks = True
    [[events]]
        stall timeout = PT1M
        abort on stall timeout = True
[scheduling]
    [[graph]]
        R1 = "spawner & holdrelease => STUFF & TOAST & CATS & DOGS & stop"
[runtime]
    [[holdrelease]]
        script = """
            cylc__job__wait_cylc_message_started
            cylc__job__poll_grep_workflow_log -E '1/foo .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/bar .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/cheese .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/jam .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/cat1 .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/cat2 .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/dog1 .* spawned'
            cylc__job__poll_grep_workflow_log -E '1/dog2 .* spawned'
            cylc hold "${CYLC_WORKFLOW_ID}//1/*FF"  # inexact fam
            cylc hold "${CYLC_WORKFLOW_ID}//1/TOAST"  # exact fam
            cylc hold "${CYLC_WORKFLOW_ID}//1/cat*"  # inexact tasks
            cylc hold "${CYLC_WORKFLOW_ID}//1/dog1"  # exact tasks
        """
    [[STUFF]]
    [[TOAST]]
    [[STOP]]
    [[CATS, DOGS]]
    [[cat1, cat2]]
        inherit = CATS
    [[dog1, dog2]]
        inherit = DOGS
    [[foo, bar]]
        inherit = STUFF
        script = true
    [[cheese, jam]]
        inherit = TOAST
        script = true
    [[stop]]
        inherit = STOP
        script = """
            sleep 5
            cylc stop "${CYLC_WORKFLOW_ID}"
        """
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${WORKFLOW_NAME}"

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --debug --no-detach --abort-if-any-task-fails "${WORKFLOW_NAME}"

# Should shut down with all the held tasks in the held state, and 2/dog
# finished and gone from the task pool.

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT cycle, name, status, is_held FROM task_pool' | sort > task-pool.out
cmp_ok task-pool.out <<__OUT__
1|bar|waiting|1
1|cat1|waiting|1
1|cat2|waiting|1
1|cheese|waiting|1
1|dog1|waiting|1
1|foo|waiting|1
1|jam|waiting|1
__OUT__

purge
