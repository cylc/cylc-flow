#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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
# Test cylc insert command for a task that has already run.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE insert-old
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run -v -v --reference-test --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-suite-err
RUN_DIR=$(cylc get-global-config --print-run-dir)
cp $RUN_DIR/$SUITE_NAME/log/suite/err $TEST_NAME
# Note: this will be sensitive to deprecation warnings, etc... but we need it
# to catch the DatabaseIntegrityError and friends.
cmp_ok $TEST_NAME </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-db-end
RUN_DIR=$(cylc get-global-config --print-run-dir)
run_ok "$TEST_NAME" sqlite3 $RUN_DIR/$SUITE_NAME/cylc-suite.db \
    "select name, cycle, submit_num, status from task_states order by name, cycle"
cmp_ok "$TEST_NAME.stdout" <<'__OUT__'
foo|20140101T0000Z|1|succeeded
foo|20140102T0000Z|1|succeeded
foo|20140103T0000Z|1|succeeded
foo|20140104T0000Z|1|succeeded
foo|20140105T0000Z|0|held
foo_cold|20140101T0000Z|2|succeeded
reinsert_foo|20140102T0000Z|1|succeeded
__OUT__
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
