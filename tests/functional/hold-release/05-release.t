#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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

# Test task and family release via exact and inexact name matches.
. "$(dirname "$0")/test_header"

set_test_number 3
 
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[cylc]
    [[events]]
        timeout = PT1M
        abort on timeout = True
        abort if any task fails = True
[scheduling]
    [[graph]]
        R1 = "spawner & holdrelease => STUFF & TOAST & CATS & DOGS & stop"
[runtime]
    [[holdrelease]]
        script = """
wait
cylc hold $CYLC_SUITE_NAME
cylc__job__poll_grep_suite_log 'Suite held.'
cylc release ${CYLC_SUITE_NAME} '*FF.1'  # inexact fam
cylc release ${CYLC_SUITE_NAME} 'TOAST.1'  # exact fam
cylc release ${CYLC_SUITE_NAME} 'cat*.1'  # inexact tasks
cylc release ${CYLC_SUITE_NAME} 'dog1.1'  # exact tasks
cylc release ${CYLC_SUITE_NAME} 'stop.1'  # exact tasks

# TODO: finished tasks are not removed if held: should this be the case?
# (is this related to killed tasks being held to prevent retries?)
cylc release ${CYLC_SUITE_NAME} 'spawner.1'
cylc release ${CYLC_SUITE_NAME} 'holdrelease.1'
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
        cylc__job__poll_grep_suite_log '\[dog1\.1\] -task proxy removed (finished)'
        cylc stop "${CYLC_SUITE_NAME}"
        """
__SUITERC__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"

# Should shut down with all non-released tasks in the held state, and dog1.1
# finished and gone from the task pool.

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle, name, status, is_held FROM task_pool' > task-pool.out
cmp_ok task-pool.out <<__OUT__
1|dog2|waiting|1
__OUT__

purge_suite "${SUITE_NAME}"
