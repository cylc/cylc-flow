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
# Test restarting a simple suite with a task still running (orphaned)
if [[ -z ${TEST_DIR:-} ]]; then
    . $(dirname $0)/test_header
fi
#-------------------------------------------------------------------------------
set_test_number 7
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE running
cp "$TEST_SOURCE_DIR/lib/suite-runtime-restart.rc" "$TEST_DIR/$SUITE_NAME/"
export TEST_DIR
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
cmp_ok "$TEST_NAME.stderr" </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --debug --no-detach $SUITE_NAME
#-------------------------------------------------------------------------------
sleep 10
TEST_NAME=$TEST_NAME_BASE-restart-run
suite_run_ok $TEST_NAME cylc restart --debug --no-detach $SUITE_NAME
#-------------------------------------------------------------------------------
if ! which sqlite3 > /dev/null; then
    skip 3 "sqlite3 not installed?"
    purge_suite "${SUITE_NAME}"
    exit 0
fi
grep_ok "running_task|20130923T0000Z|1|1|running" \
    $TEST_DIR/pre-restart-db
contains_ok $TEST_DIR/post-restart-db <<'__DB_DUMP__'
finish|20130923T0000Z|0||waiting
running_task|20130923T0000Z|1|1|running
shutdown|20130923T0000Z|1|1|succeeded
__DB_DUMP__
"${TEST_SOURCE_DIR}/bin/ctb-select-task-states" "${SUITE_RUN_DIR}" \
    > "${TEST_DIR}/db"
contains_ok $TEST_DIR/db <<'__DB_DUMP__'
finish|20130923T0000Z|1|1|succeeded
output_states|20130923T0000Z|1|1|succeeded
running_task|20130923T0000Z|1|1|succeeded
shutdown|20130923T0000Z|1|1|succeeded
__DB_DUMP__
#-------------------------------------------------------------------------------
purge_suite "$SUITE_NAME"
