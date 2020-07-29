#!/usr/bin/env bash
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

# Test task and family hold via exact and inexact name matches.
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
cylc__job__poll_grep_suite_log -F 'spawned foo.1'
cylc__job__poll_grep_suite_log -F 'spawned bar.1'
cylc__job__poll_grep_suite_log -F 'spawned cheese.1'
cylc__job__poll_grep_suite_log -F 'spawned jam.1'
cylc__job__poll_grep_suite_log -F 'spawned cat1.1'
cylc__job__poll_grep_suite_log -F 'spawned cat2.1'
cylc__job__poll_grep_suite_log -F 'spawned dog1.1'
cylc__job__poll_grep_suite_log -F 'spawned dog2.1'
cylc hold ${CYLC_SUITE_NAME} '*FF.1'  # inexact fam
cylc hold ${CYLC_SUITE_NAME} 'TOAST.1'  # exact fam
cylc hold ${CYLC_SUITE_NAME} 'cat*.1'  # inexact tasks
cylc hold ${CYLC_SUITE_NAME} 'dog1.1'  # exact tasks
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
        cylc stop "${CYLC_SUITE_NAME}"
        """
__SUITERC__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${SUITE_NAME}"

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --debug --no-detach "${SUITE_NAME}"

# Should shut down with all the held tasks in the held state, and dog.2
# finished and gone from the task pool.

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle, name, status, is_held FROM task_pool' > task-pool.out
cmp_ok task-pool.out <<__OUT__
1|foo|waiting|1
1|bar|waiting|1
1|cheese|waiting|1
1|jam|waiting|1
1|cat1|waiting|1
1|cat2|waiting|1
1|dog1|waiting|1
__OUT__

purge_suite "${SUITE_NAME}"
