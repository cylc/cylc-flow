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
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 49
#-------------------------------------------------------------------------------
LOG_SCRIPT="$CYLC_DIR/lib/cylc/suite_logging.py"
TMP_DIR=$(mktemp -d)
#-------------------------------------------------------------------------------
# Test log file rolling.
mkdir "$TMP_DIR/test_roll"
TEST_NAME=$TEST_NAME_BASE-test-roll
run_ok $TEST_NAME python "$LOG_SCRIPT" "$TMP_DIR" "test-roll"
CMP_DIR="$TEST_SOURCE_DIR/01-suite-logging/test_roll"
LOG_DIR="$TMP_DIR/test_roll"
LOG_FILES=($(ls $LOG_DIR))
CMP_FILES=($(ls $CMP_DIR))
LENGTH=${#LOG_FILES[@]}
for N in $(seq 0 1 $(expr ${#LOG_FILES[@]} - 1)); do
    cmp_ok "$LOG_DIR/${LOG_FILES[$N]}" "$CMP_DIR/${CMP_FILES[$N]}"
done
#-------------------------------------------------------------------------------
# Test back compatability to old logging system (i.e. log.1, log.2, ..., log.n)
mkdir "$TMP_DIR/test_back_compat"
TEST_NAME=$TEST_NAME_BASE-test-back-compat
run_ok $TEST_NAME python "$LOG_SCRIPT" "$TMP_DIR" "test-back-compat"
CMP_DIR="$TEST_SOURCE_DIR/01-suite-logging/test_back_compat"
LOG_DIR="$TMP_DIR/test_back_compat"
LOG_FILES=($(ls $LOG_DIR))
CMP_FILES=($(ls $CMP_DIR))
LENGTH=${#LOG_FILES[@]}
for N in $(seq 0 1 $(expr ${#LOG_FILES[@]} - 1)); do
    cmp_ok "$LOG_DIR/${LOG_FILES[$N]}" "$CMP_DIR/${CMP_FILES[$N]}"
done
ls "$LOG_DIR" > "$TMP_DIR/log_summary"
grep_ok "err\.0" "$TMP_DIR/log_summary"
grep_ok "err\.1" "$TMP_DIR/log_summary"
grep_ok "out\.0" "$TMP_DIR/log_summary"
grep_ok "out\.1" "$TMP_DIR/log_summary"
grep_ok "log\.0" "$TMP_DIR/log_summary"
grep_ok "log\.1" "$TMP_DIR/log_summary"
#-------------------------------------------------------------------------------
# Test housekeeping.
mkdir "$TMP_DIR/test_housekeep"
TEST_NAME=$TEST_NAME_BASE-test-housekeep
run_ok $TEST_NAME python "$LOG_SCRIPT" "$TMP_DIR" "test-housekeep"
CMP_DIR="$TEST_SOURCE_DIR/01-suite-logging/test_back_compat"
LOG_DIR="$TMP_DIR/test_back_compat"
LOG_FILES=($(ls $LOG_DIR))
CMP_FILES=($(ls $CMP_DIR))
TEST_NAME=$TEST_NAME-length
if (( ${#LOG_FILES[@]} == 15 )); then ok $TEST_NAME; else fail $TEST_NAME; fi
for N in $(seq 0 1 $(expr ${#LOG_FILES[@]} - 1)); do
    cmp_ok "$LOG_DIR/${LOG_FILES[$N]}" "$CMP_DIR/${CMP_FILES[$N]}"
done
#-------------------------------------------------------------------------------
rm -rf $TMP_DIR
#-------------------------------------------------------------------------------
