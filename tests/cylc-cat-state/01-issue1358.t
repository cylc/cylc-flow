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
# Test the state dump gets updated if a task is removed when nothing else is
# happening (github #1358).
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 2
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate $SUITE_NAME
#-------------------------------------------------------------------------------
set -x
# Run suite.
cylc run $SUITE_NAME
# Wait for task foo to fail.
cylc suite-state $SUITE_NAME --task=foo --cycle=1 \
    --status=failed --max-polls=10 --interval=2
# Remove it.
cylc remove $SUITE_NAME foo 1
# (wait till foo is removed)
sleep 5
# Record the state dump.
cylc cat-state -d $SUITE_NAME > state.out
# Stop the suite.
cylc stop $SUITE_NAME
# Do the test.
cmp_ok state.out << __DONE__
bar, 1, waiting, spawned
baz, 1, waiting, spawned
__DONE__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
