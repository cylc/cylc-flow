#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test restart with held (retrying) task
. "$(dirname "$0")/test_header"
set_test_number 6
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run "${SUITE_NAME}" --debug --until=2016
if ! which sqlite3 > /dev/null; then
    skip 1 "sqlite3 not installed?"
else
    sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT * FROM task_pool ORDER BY cycle, name' \
        >'task-pool.out'
    contains_ok 'task-pool.out' <<__OUT__
2016|t2|1|held|retrying
2017|t1|0|waiting|
2017|t2|0|waiting|
__OUT__
fi
suite_run_ok "${TEST_NAME_BASE}-restart" \
    cylc restart "${SUITE_NAME}" --debug --until=2017
grep_ok 'INFO - + t2\.2016 held (retrying)' "${SUITE_RUN_DIR}/log/suite/log"
if ! which sqlite3 > /dev/null; then
    skip 1 "sqlite3 not installed?"
else
    sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT * FROM task_pool ORDER BY cycle, name' \
        >'task-pool.out'
    contains_ok 'task-pool.out' <<__OUT__
2016|t2|1|succeeded|
2018|t1|0|waiting|
2018|t2|0|waiting|
__OUT__
fi
purge_suite "${SUITE_NAME}"
exit
