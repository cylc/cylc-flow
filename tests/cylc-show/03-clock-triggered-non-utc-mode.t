#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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
install_suite $TEST_NAME_BASE clock-triggered-non-utc-mode
#-------------------------------------------------------------------------------
TEST_SHOW_OUTPUT_PATH="$PWD/$TEST_NAME_BASE-show.stdout"
TZ_OFFSET_EXTENDED=$(date +%:::z | sed "/^%/d")
if [[ -z "$TZ_OFFSET_EXTENDED" ]]; then
    skip 3 "'date' command doesn't support '%:::z'"
    exit 0
fi
if [[ TZ_OFFSET_EXTENDED -eq "+00" ]]; then
    TZ_OFFSET_EXTENDED=Z
fi
TZ_OFFSET_BASIC=${TZ_OFFSET_EXTENDED/:/}
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-validate
run_ok $TEST_NAME cylc validate \
    --set=TEST_SHOW_OUTPUT_PATH="$TEST_SHOW_OUTPUT_PATH" \
    --set=TZ_OFFSET_BASIC="$TZ_OFFSET_BASIC" "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-run
suite_run_ok $TEST_NAME cylc run --reference-test --debug \
    --set=TEST_SHOW_OUTPUT_PATH="$TEST_SHOW_OUTPUT_PATH" \
    --set=TZ_OFFSET_BASIC="$TZ_OFFSET_BASIC" "$SUITE_NAME"
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-show
cmp_ok $TEST_NAME.stdout <<__SHOW_OUTPUT__
TASK foo.20140808T0900$TZ_OFFSET_BASIC in suite $SUITE_NAME:
  

PREREQUISITES (- => not satisfied):
  - show.20140808T0900$TZ_OFFSET_BASIC succeeded
OUTPUTS (- => not completed):
  - foo.20140808T0900$TZ_OFFSET_BASIC succeeded
  - foo.20140808T0900$TZ_OFFSET_BASIC submitted
  - foo.20140808T0900$TZ_OFFSET_BASIC started
Other:
  o  Clock trigger time reached ... True
  o  Triggers at ... 2014-08-08T09:05:00$TZ_OFFSET_EXTENDED

NOTE: for tasks that have triggered already, prerequisites are
shown here in the state they were in at the time of triggering.
__SHOW_OUTPUT__
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
