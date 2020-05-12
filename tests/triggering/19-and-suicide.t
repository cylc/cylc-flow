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
# Test "and" outputs from 2 tasks triggering suicide.
# https://github.com/cylc/cylc-flow/issues/2655
. "$(dirname "$0")/test_header"
set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
DBFILE="$RUN_DIR/${SUITE_NAME}/log/db"
sqlite3 "${DBFILE}" 'SELECT * FROM task_pool ORDER BY name;' >'sqlite3.out'
cmp_ok 'sqlite3.out' <<'__OUT__'
1|t0|1|succeeded|0
1|t1|1|failed|0
1|t2|1|succeeded|0
__OUT__

purge_suite "${SUITE_NAME}"
exit
