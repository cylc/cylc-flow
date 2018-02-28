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
# Test upgrade of 6.10.X database + state on restart.
. "$(dirname "$0")/test_header"

which sqlite3 > /dev/null || skip_all

set_test_number 18
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

mkdir -p "${SUITE_RUN_DIR}/state"
sqlite3 "${SUITE_RUN_DIR}/state/cylc-suite.db" <"cylc-suite-db.dump"
cp -p 'state/state' "${SUITE_RUN_DIR}/state/"
run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-restart" cylc restart --debug --no-detach "${SUITE_NAME}"
sed 's/^.* INFO - //' "${SUITE_RUN_DIR}/log/suite/log" >'edited.log'
contains_ok 'edited.log' <<'__OUT__'
LOADING suite parameters
+ initial cycle point = 20000101T0000Z
+ final cycle point = 20030101T0000Z
LOADING broadcast states
+ [root.*] [environment]CYLC_TEST_VAR=hello
LOADING task run times
LOADING task proxies
+ bar.20030101T0000Z succeeded
+ bar.20040101T0000Z held
+ foo.20040101T0000Z held
__OUT__
exists_ok "${SUITE_RUN_DIR}/state.tar.gz"
exists_ok "${SUITE_RUN_DIR}/.service/db" 
exists_ok "${SUITE_RUN_DIR}/log/db" 

run_ok "${TEST_NAME_BASE}-checkpoint_id" \
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT id,event FROM checkpoint_id ORDER BY id'
cmp_ok "${TEST_NAME_BASE}-checkpoint_id.stdout" <<__OUT__
0|latest
1|restart
__OUT__
run_ok "${TEST_NAME_BASE}-suite_params" \
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT key,value FROM suite_params ORDER BY key'
sed -i "s/$(cylc --version)/<SOME-VERSION>/g" \
    "${TEST_NAME_BASE}-suite_params.stdout"
cmp_ok "${TEST_NAME_BASE}-suite_params.stdout" <<__OUT__
UTC_mode|True
cylc_version|<SOME-VERSION>
final_point|20050101T0000Z
initial_point|20000101T0000Z
run_mode|live
__OUT__
run_ok "${TEST_NAME_BASE}-suite_params_checkpoints" \
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT key,value FROM suite_params_checkpoints WHERE id==1 ORDER BY key'
cmp_ok "${TEST_NAME_BASE}-suite_params_checkpoints.stdout" <<__OUT__
final_point|20030101T0000Z
initial_point|20000101T0000Z
run_mode|live
__OUT__
run_ok "${TEST_NAME_BASE}-task_pool" \
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle,name,spawned,status FROM task_pool ORDER BY cycle, name'
cmp_ok "${TEST_NAME_BASE}-task_pool.stdout" <<__OUT__
20050101T0000Z|bar|1|succeeded
20060101T0000Z|bar|0|waiting
20060101T0000Z|foo|0|waiting
__OUT__
run_ok "${TEST_NAME_BASE}-task_pool_checkpoints" \
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle,name,spawned,status FROM task_pool_checkpoints 
     WHERE id==1 ORDER BY cycle, name'
cmp_ok "${TEST_NAME_BASE}-task_pool_checkpoints.stdout" <<__OUT__
20030101T0000Z|bar|1|succeeded
20040101T0000Z|bar|0|held
20040101T0000Z|foo|0|held
__OUT__
run_ok "${TEST_NAME_BASE}-task_states" \
    sqlite3 "${SUITE_RUN_DIR}/log/db" \
    'SELECT cycle,name,status FROM task_states ORDER BY cycle, name'
cmp_ok "${TEST_NAME_BASE}-task_states.stdout" <<__OUT__
20000101T0000Z|bar|succeeded
20000101T0000Z|foo|succeeded
20010101T0000Z|bar|succeeded
20010101T0000Z|foo|succeeded
20020101T0000Z|bar|succeeded
20020101T0000Z|foo|succeeded
20030101T0000Z|bar|succeeded
20030101T0000Z|foo|succeeded
20040101T0000Z|bar|succeeded
20040101T0000Z|foo|succeeded
20050101T0000Z|bar|succeeded
20050101T0000Z|foo|succeeded
20060101T0000Z|bar|waiting
20060101T0000Z|foo|waiting
__OUT__

purge_suite "${SUITE_NAME}"
exit
