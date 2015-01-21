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
# Test restarting a suite with pre-initial cycle dependencies
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 4
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE pre-init
export TEST_DIR
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --debug $SUITE_NAME
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-monitor
START_TIME=$(date +%s)
export START_TIME SUITE_NAME
run_ok $TEST_NAME bash <<'__SCRIPT__'
while [[ -e $HOME/.cylc/ports/$SUITE_NAME || ! -e $TEST_DIR/suite-stopping ]]; do
    if [[ $(date +%s) > $(( START_TIME + 120 )) ]]; then
        echo "[ERROR] Suite Timeout - shutting down..." >&2
        cylc shutdown --now --kill $SUITE_NAME &
        exit 1
    fi
    sleep 1
done
__SCRIPT__

RUN_DIR=$(cylc get-global-config --print-run-dir)
sqlite3 $RUN_DIR/$SUITE_NAME/cylc-suite.db \
                "select name, cycle, status
                 from task_states
                 order by name, cycle" > final-state

contains_ok final-state $TEST_SOURCE_DIR/pre-init/ref-state

#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
