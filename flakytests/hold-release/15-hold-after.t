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
# Test cylc hold --after CYCLE_POINT.
# Test cylc run --hold-after CYCLE_POINT.

. "$(dirname "$0")/test_header"
set_test_number 4
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
# cylc hold --after=...
suite_run_ok "${TEST_NAME_BASE}-1" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT * FROM task_pool WHERE cycle=="20140102T0000Z" ORDER BY name' \
    >'taskpool.out'
cmp_ok 'taskpool.out' <<'__OUT__'
20140102T0000Z|bar|0|waiting|1
20140102T0000Z|foo|0|waiting|1
__OUT__
# cylc run --hold-after=...
suite_run_ok "${TEST_NAME_BASE}-2" \
    cylc run --hold-after='20140101T1200Z' --reference-test --debug \
    --no-detach "${SUITE_NAME}"

purge_suite "${SUITE_NAME}"
exit
