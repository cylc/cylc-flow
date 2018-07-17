#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & contributors
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
# Test that removing a task from the graph works OK.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 13
#-------------------------------------------------------------------------------
# test reporting of added tasks

# install suite
install_suite $TEST_NAME_BASE graphing-change
LOG_FILE="$HOME/cylc-run/$SUITE_NAME/log/suite/log"
TEST_NAME=$TEST_NAME_BASE-add-run

# start suite in held mode
run_ok $TEST_NAME cylc run --hold $SUITE_NAME
sleep 5

# change the suite.rc file
cp "$TEST_SOURCE_DIR/graphing-change/suite-1.rc" "$TEST_DIR/$SUITE_NAME/suite.rc"

# reload suite
TEST_NAME=$TEST_NAME_BASE-add-reload
run_ok $TEST_NAME cylc reload $SUITE_NAME
while (($(grep -c 'Reload completed' "${LOG_FILE}" || true) < 1)); do
    sleep 1  # make sure reload 1 completes
done

# check suite log
grep_ok "Added task: 'one'" $LOG_FILE
#-------------------------------------------------------------------------------
# test reporting or removed tasks

# change the suite.rc file
cp "$TEST_SOURCE_DIR/graphing-change/suite.rc" "$TEST_DIR/$SUITE_NAME/suite.rc"

# reload suite
TEST_NAME=$TEST_NAME_BASE-remove-reload
run_ok $TEST_NAME cylc reload $SUITE_NAME
while (($(grep -c 'Reload completed' "${LOG_FILE}" || true) < 2)); do
    sleep 1  # make sure reload 2 completes
done

# check suite log
grep_ok "Removed task: 'one'" $LOG_FILE
#-------------------------------------------------------------------------------
# test reporting of adding / removing / swapping tasks

# set suite running
TEST_NAME=$TEST_NAME_BASE-unhold
run_ok $TEST_NAME cylc unhold $SUITE_NAME

# change the suite.rc file
cp "$TEST_SOURCE_DIR/graphing-change/suite-2.rc" "$TEST_DIR/$SUITE_NAME/suite.rc"

# reload suite
TEST_NAME=$TEST_NAME_BASE-swap-reload
run_ok $TEST_NAME cylc reload $SUITE_NAME
while (($(grep -c 'Reload completed' "${LOG_FILE}" || true) < 3)); do
    sleep 1  # make sure reload 3 completes
done

# check suite log
TEST_NAME=$TEST_NAME_BASE-swap-log
grep_ok "Added task: 'one'" $LOG_FILE
grep_ok "Added task: 'add'" $LOG_FILE
grep_ok "Added task: 'boo'" $LOG_FILE
grep_ok "\[bar.*\].*orphaned" $LOG_FILE
grep_ok "\[bol.*\].*orphaned" $LOG_FILE

# shutdown suite
TEST_NAME=$TEST_NAME_BASE-shutdown
run_ok $TEST_NAME cylc shutdown $SUITE_NAME

# tidy up
purge_suite $SUITE_NAME
#-------------------------------------------------------------------------------
