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
# Test "cylc run SUITE now" and "cylc run --icp=now SUITE".
# And "cylc run --icp=next(...) SUITE" and "cylc run --icp=previous(...) SUITE"
# And restart.

. "$(dirname "$0")/test_header"
set_test_number 13
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        abort on stalled = true
        abort on inactivity = true
        inactivity = PT1M
[scheduling]
    [[graph]]
        R1 = foo
[runtime]
    [[foo]]
        script = wait; cylc stop --now --now "${CYLC_SUITE_NAME}"
__SUITERC__

run_ok "${TEST_NAME_BASE}-validate" cylc validate --icp='now' "${SUITE_NAME}"

# Test "cylc run SUITE now"
suite_run_ok "${TEST_NAME_BASE}-run-now" \
    cylc run --debug --no-detach "${SUITE_NAME}" 'now'
MY_CYCLE="$(sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT cycle FROM task_pool')"
suite_run_ok "${TEST_NAME_BASE}-restart-now" \
    cylc restart --debug --no-detach "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task_pool.out'
cmp_ok 'task_pool.out' <<__OUT__
${MY_CYCLE}|foo|1|succeeded|0
__OUT__

# Tests:
# "cylc run --icp=now SUITE"
# "cylc run --icp=next(T00) SUITE"
# "cylc run --icp=previous(T00) SUITE"
for ICP in 'now' 'next(T00)' 'previous(T00)'; do
    suite_run_ok "${TEST_NAME_BASE}-run-icp-now" \
        cylc run --debug --no-detach --icp="${ICP}" "${SUITE_NAME}"
    MY_CYCLE="$(sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT cycle FROM task_pool')"
    suite_run_ok "${TEST_NAME_BASE}-restart-icp-now" \
        cylc restart --debug --no-detach "${SUITE_NAME}"
    sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT * FROM task_pool' >'task_pool.out'
    cmp_ok 'task_pool.out' <<__OUT__
${MY_CYCLE}|foo|1|succeeded|0
__OUT__
done

purge_suite "${SUITE_NAME}"
exit
