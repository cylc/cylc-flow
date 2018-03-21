#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA
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
if which sqlite3 > '/dev/null'; then
    sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT outputs FROM task_outputs' \
        >'sqlite3.out'
    cmp_ok 'sqlite3.out' <<<'hello=hello'
else
    skip 1 'sqlite3 not installed?'
fi
suite_run_fail "${TEST_NAME_BASE}-restart-1" \
    cylc restart --no-detach "${SUITE_NAME}"
sed -i 's/#\(startup handler\)/\1/; s/\(abort on stalled\)/#\1/' 'suite.rc'
suite_run_ok "${TEST_NAME_BASE}-restart-2" \
    cylc restart --debug --no-detach --reference-test "${SUITE_NAME}"
if which sqlite3 > '/dev/null'; then
    sqlite3 "${SUITE_RUN_DIR}/log/db" 'SELECT outputs FROM task_outputs' \
        >'sqlite3.out'
    cmp_ok 'sqlite3.out' <<'__OUT__'
greet=greeting
hello=hello
__OUT__
else
    skip 1 'sqlite3 not installed?'
fi
purge_suite "${SUITE_NAME}"
exit
