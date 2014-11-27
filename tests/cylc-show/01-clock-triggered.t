#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
# Test cylc show for a clock triggered task
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 3
#-------------------------------------------------------------------------------
install_suite $TEST_NAME_BASE clock-triggered
#-------------------------------------------------------------------------------
TEST_SHOW_OUTPUT_PATH="$PWD/$TEST_NAME_BASE-show.stdout"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate \
    --set=TEST_OUTPUT_PATH="$TEST_SHOW_OUTPUT_PATH" "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug \
    --set=TEST_OUTPUT_PATH="$TEST_SHOW_OUTPUT_PATH" "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-show
cmp_ok $TEST_NAME.stdout <<__SHOW_OUTPUT__
TASK foo.20141106T0900Z in suite $SUITE_NAME:
  

PREREQUISITES (- => not satisfied):
  - show.20141106T0900Z succeeded
OUTPUTS (- => not completed):
  - foo.20141106T0900Z submitted
  - foo.20141106T0900Z succeeded
  - foo.20141106T0900Z started
Other:
  o  Clock trigger time reached ... True
  o  Triggers at ... 2014-11-06T09:05:00Z

NOTE: for tasks that have triggered already, prerequisites are
shown here in the state they were in at the time of triggering.
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
