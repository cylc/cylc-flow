#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
# Test intercycle dependencies.
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 6
#-------------------------------------------------------------------------------
# test initial and final cycle point special notation (^, $)
TEST_NAME=$TEST_NAME_BASE
install_suite $TEST_NAME_BASE $TEST_NAME_BASE
TEST_NAME=$TEST_NAME_BASE-run
run_ok $TEST_NAME cylc run $SUITE_NAME

sleep 10  # wait for suite to complete

TEST_NAME=$TEST_NAME_BASE-out
grep_ok "\[foo\.20160101T0000Z\]" "$HOME/cylc-run/$SUITE_NAME/log/suite/log"
grep_ok "\[bar\.20160101T0000Z\]" "$HOME/cylc-run/$SUITE_NAME/log/suite/log"
grep_ok "\[baz\.20160101T0100Z\]" "$HOME/cylc-run/$SUITE_NAME/log/suite/log"
grep_ok "\[boo\.20160101T2300Z\]" "$HOME/cylc-run/$SUITE_NAME/log/suite/log"
grep_ok "\[bot\.20160102T0000Z\]" "$HOME/cylc-run/$SUITE_NAME/log/suite/log"
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
