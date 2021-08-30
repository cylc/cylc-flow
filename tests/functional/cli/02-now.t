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
# Test "cylc play --icp=now WORKFLOW".
# And "cylc play --icp=next(...) WORKFLOW" and "cylc play --icp=previous(...) WORKFLOW"
# And restart.

. "$(dirname "$0")/test_header"
set_test_number 10
init_workflow "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on stall = true
        abort on inactivity = true
        inactivity = PT1M
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = cylc__job__wait_cylc_message_started; cylc stop --now --now "${CYLC_WORKFLOW_NAME}"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate --icp='now' "${WORKFLOW_NAME}"

for ICP in 'now' 'next(T00)' 'previous(T00)'; do
    workflow_run_ok "${TEST_NAME_BASE}-run-icp-${ICP}" \
        cylc play --debug --no-detach --icp="${ICP}" "${WORKFLOW_NAME}"

    workflow_run_ok "${TEST_NAME_BASE}-restart-icp-${ICP}" \
        cylc play --debug --no-detach "${WORKFLOW_NAME}"

    sqlite3 "${WORKFLOW_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task_pool.out'
    cmp_ok 'task_pool.out' <'/dev/null'
    # TODO - is this test still useful?
    # Consider checking the task succeeded in the task_states table, instead.
    # pre-SoD:
    # sqlite3 "${WORKFLOW_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task_pool.out'
    # cmp_ok 'task_pool.out' <<__OUT__
    # ${MY_CYCLE}|foo|1|succeeded|0
    # __OUT__

    delete_db
done

purge
exit
