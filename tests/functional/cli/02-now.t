#!/usr/bin/env bash
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
# Test "cylc play --icp=now SUITE".
# And "cylc play --icp=next(...) SUITE" and "cylc play --icp=previous(...) SUITE"
# And restart.

. "$(dirname "$0")/test_header"
set_test_number 10
init_suite "${TEST_NAME_BASE}" <<'__FLOW_CONFIG__'
[scheduler]
    [[events]]
        abort on stalled = true
        abort on inactivity = true
        inactivity = PT1M
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = cylc__job__wait_cylc_message_started; cylc stop --now --now "${CYLC_SUITE_NAME}"
__FLOW_CONFIG__

run_ok "${TEST_NAME_BASE}-validate" cylc validate --icp='now' "${SUITE_NAME}"

for ICP in 'now' 'next(T00)' 'previous(T00)'; do
    suite_run_ok "${TEST_NAME_BASE}-run-icp-${ICP}" \
        cylc play --debug --no-detach --icp="${ICP}" "${SUITE_NAME}"

    suite_run_ok "${TEST_NAME_BASE}-restart-icp-${ICP}" \
        cylc play --debug --no-detach "${SUITE_NAME}"

    sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task_pool.out'
    cmp_ok 'task_pool.out' <'/dev/null'
    # TODO - is this test still useful?
    # Consider checking the task succeeded in the task_states table, instead.
    # pre-SoD:
    # sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task_pool.out'
    # cmp_ok 'task_pool.out' <<__OUT__
    # ${MY_CYCLE}|foo|1|succeeded|0
    # __OUT__

    delete_db
done

purge
exit
