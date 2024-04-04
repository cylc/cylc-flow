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
# Test that spawned children of released tasks are held when the workflow has
# a hold point.
. "$(dirname "$0")/test_header"
set_test_number 2
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduling]
    [[dependencies]]
        R1 = "foo => bar"
[runtime]
   [[foo, bar]]
        script = cylc__job__wait_cylc_message_started; true
__FLOW_CONFIG__

workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --hold-after=0 --debug "${WORKFLOW_NAME}"

cylc release "${WORKFLOW_NAME}//1/foo"
# 1/foo should run and spawn 1/bar as waiting and held

poll_grep_workflow_log -E '1/bar.* added to active task pool'

sqlite3 "${WORKFLOW_RUN_DIR}/log/db" \
    'SELECT cycle, name, status, is_held FROM task_pool' > task-pool.out

cmp_ok task-pool.out <<__OUT__
1|bar|waiting|1
__OUT__

cylc stop --now --now "${WORKFLOW_NAME}"

purge
