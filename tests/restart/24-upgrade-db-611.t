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
#-------------------------------------------------------------------------------
# Test upgrade of 6.11.X database on restart.
. "$(dirname "$0")/test_header"

which sqlite3 > /dev/null || skip_all "sqlite3 not installed?"
set_test_number 8

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

mkdir -p "${SUITE_RUN_DIR}/state"
sqlite3 "${SUITE_RUN_DIR}/state/cylc-suite.db" <"cylc-suite-db.dump"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-restart" cylc restart --debug --no-detach \
    "${SUITE_NAME}"
sed -i 's/^.* INFO - //' "${TEST_NAME_BASE}-restart.stdout"
exists_ok "${SUITE_RUN_DIR}/.service/db" 
exists_ok "${SUITE_RUN_DIR}/log/db" 
exists_fail "${SUITE_RUN_DIR}/cylc-suite-private.db" 
exists_fail "${SUITE_RUN_DIR}/cylc-suite-public" 
exists_fail "${SUITE_RUN_DIR}/cylc-suite-env" 
sqlite3 "${SUITE_RUN_DIR}/log/db" '.schema task_pool' >'task_pool.schema'
cmp_ok 'task_pool.schema' \
    <<<'CREATE TABLE task_pool(cycle TEXT, name TEXT, spawned INTEGER, status TEXT, hold_swap TEXT, PRIMARY KEY(cycle, name));'

purge_suite "${SUITE_NAME}"
exit
