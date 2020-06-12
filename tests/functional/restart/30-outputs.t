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
# Test task outputs status is retained on restart
. "$(dirname "$0")/test_header"

set_test_number 6
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_fail "${TEST_NAME_BASE}-run" cylc run --no-detach "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT outputs FROM task_outputs' \
    >'sqlite3.out'
cmp_json 'sqlite3.out' 'sqlite3.out' <<<'{"hello": "hello"}'
suite_run_fail "${TEST_NAME_BASE}-restart-1" \
    cylc restart --no-detach "${SUITE_NAME}"
sed -i 's/#\(stalled handler\)/\1/; s/\(abort on stalled\)/#\1/' 'suite.rc'
suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc restart --debug --no-detach --reference-test "${SUITE_NAME}"
sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT outputs FROM task_outputs' \
    >'sqlite3.out'
cmp_json 'sqlite3.out' 'sqlite3.out' \
    <<<'{"hello": "hello", "greet": "greeting"}'
purge_suite "${SUITE_NAME}"
exit
