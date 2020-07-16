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
# Test remote host settings.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_remote
set_test_number 4
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" basic
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --reference-test --debug --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-userathost
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'select user_at_host from task_jobs where name=="foo"' >'foo-host.txt'
cmp_ok 'foo-host.txt' <<<"${CYLC_TEST_OWNER}@${CYLC_TEST_HOST}"
#-------------------------------------------------------------------------------
TEST_NAME=${TEST_NAME_BASE}-hostonly
sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'select user_at_host from task_jobs where name=="bar"' >'bar-host.txt'
cmp_ok 'bar-host.txt' - <<<"${CYLC_TEST_HOST}"
#-------------------------------------------------------------------------------
purge_suite_remote "${CYLC_TEST_HOST}" "${SUITE_NAME}"
purge_suite "${SUITE_NAME}"
exit
