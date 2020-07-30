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
# Test that spawned children of tasks released in a held suite, are held.
. "$(dirname "$0")/test_header"
set_test_number 2
init_suite "${TEST_NAME_BASE}" <<'__SUITERC__'
[scheduling]
   [[dependencies]]
        R1 = "foo => bar"
[runtime]
   [[foo, bar]]
        script = true
__SUITERC__

suite_run_ok "${TEST_NAME_BASE}-run" cylc run --hold "${SUITE_NAME}"

cylc release "${SUITE_NAME}" foo.1
# foo.1 should run and spawn bar.1 as waiting

poll_grep_suite_log 'spawned bar\.1'

sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle, name, status, is_held FROM task_pool' > task-pool.out

cmp_ok task-pool.out <<__OUT__
1|bar|waiting|1
__OUT__

cylc stop --max-polls=10 --interval=2 "${SUITE_NAME}"

purge_suite "${SUITE_NAME}"
