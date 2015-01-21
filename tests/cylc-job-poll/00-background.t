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
# Test cylc job-poll, background jobs
. $(dirname $0)/test_header

function get_fake_pid() {
    # Choose a non existent PID
    local T_JOB_ID=$RANDOM
    while ps $T_JOB_ID 1>/dev/null; do
        T_JOB_ID=$RANDOM
    done
    echo $T_JOB_ID
}
#-------------------------------------------------------------------------------
set_test_number 12
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-null
# A non-existent status file
T_ST_FILE="${PWD}/1/${TEST_NAME}/01/job.status"
mkdir -p "${PWD}/1/${TEST_NAME}/01"
T_JOB_ID=$(get_fake_pid)
run_ok $TEST_NAME cylc job-poll "${T_ST_FILE}"
cmp_ok $TEST_NAME.stdout <<__OUT__
polled ${TEST_NAME}.1 submission failed
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-submitted
# A non-existent status file
T_ST_FILE="${PWD}/1/${TEST_NAME}/01/job.status"
mkdir -p "${PWD}/1/${TEST_NAME}/01"
# Give it a real PID
sleep 60 &
T_JOB_ID=$!
cat >$T_ST_FILE <<__STATUS__
CYLC_BATCH_SYS_NAME=background
CYLC_BATCH_SYS_JOB_ID=$T_JOB_ID
__STATUS__
run_ok $TEST_NAME cylc job-poll "${T_ST_FILE}"
cmp_ok $TEST_NAME.stdout <<__OUT__
polled ${TEST_NAME}.1 submitted
__OUT__
kill $T_JOB_ID
wait $T_JOB_ID 2>/dev/null || true
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-started
# Give it a real PID
sleep 60 &
T_JOB_ID=$!
# Status file
T_ST_FILE="${PWD}/1/${TEST_NAME}/01/job.status"
mkdir -p "${PWD}/1/${TEST_NAME}/01"
T_INIT_TIME=$(date +%FT%H:%M:%S)
cat >$T_ST_FILE <<__STATUS__
CYLC_BATCH_SYS_NAME=background
CYLC_BATCH_SYS_JOB_ID=$T_JOB_ID
CYLC_JOB_PID=$T_JOB_ID
CYLC_JOB_INIT_TIME=$T_INIT_TIME
__STATUS__
run_ok $TEST_NAME cylc job-poll "${T_ST_FILE}"
cmp_ok $TEST_NAME.stdout <<__OUT__
polled ${TEST_NAME}.1 started at $T_INIT_TIME
__OUT__
kill $T_JOB_ID
wait $T_JOB_ID 2>/dev/null || true
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-succeeded
T_JOB_ID=$(get_fake_pid)
# Status file
T_ST_FILE="${PWD}/1/${TEST_NAME}/01/job.status"
mkdir -p "${PWD}/1/${TEST_NAME}/01"
T_INIT_TIME=$(date +%FT%H:%M:%S)
T_EXIT_TIME=$(date +%FT%H:%M:%S)
cat >$T_ST_FILE <<__STATUS__
CYLC_BATCH_SYS_NAME=background
CYLC_BATCH_SYS_JOB_ID=$T_JOB_ID
CYLC_JOB_PID=$T_JOB_ID
CYLC_JOB_INIT_TIME=$T_INIT_TIME
CYLC_JOB_EXIT=SUCCEEDED
CYLC_JOB_EXIT_TIME=$T_EXIT_TIME
__STATUS__
run_ok $TEST_NAME cylc job-poll "${T_ST_FILE}"
cmp_ok $TEST_NAME.stdout <<__OUT__
polled ${TEST_NAME}.1 succeeded at $T_EXIT_TIME
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-failed
T_JOB_ID=$(get_fake_pid)
# Status file
T_ST_FILE="${PWD}/1/${TEST_NAME}/01/job.status"
mkdir -p "${PWD}/1/${TEST_NAME}/01"
T_INIT_TIME=$(date +%FT%H:%M:%S)
T_EXIT_TIME=$(date +%FT%H:%M:%S)
cat >$T_ST_FILE <<__STATUS__
CYLC_BATCH_SYS_NAME=background
CYLC_BATCH_SYS_JOB_ID=$T_JOB_ID
CYLC_JOB_PID=$T_JOB_ID
CYLC_JOB_INIT_TIME=$T_INIT_TIME
CYLC_JOB_EXIT=ERR
CYLC_JOB_EXIT_TIME=$T_EXIT_TIME
__STATUS__
run_ok $TEST_NAME cylc job-poll "${T_ST_FILE}"
cmp_ok $TEST_NAME.stdout <<__OUT__
polled ${TEST_NAME}.1 failed at $T_EXIT_TIME
__OUT__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-failed-bad
T_JOB_ID=$(get_fake_pid)
# Status file
T_ST_FILE="${PWD}/1/${TEST_NAME}/01/job.status"
mkdir -p "${PWD}/1/${TEST_NAME}/01"
T_INIT_TIME=$(date +%FT%H:%M:%S)
T_EXIT_TIME=$(date +%FT%H:%M:%S)
cat >$T_ST_FILE <<__STATUS__
CYLC_BATCH_SYS_NAME=background
CYLC_BATCH_SYS_JOB_ID=$T_JOB_ID
CYLC_JOB_PID=$T_JOB_ID
CYLC_JOB_INIT_TIME=$T_INIT_TIME
__STATUS__
run_ok $TEST_NAME cylc job-poll "${T_ST_FILE}"
cmp_ok $TEST_NAME.stdout <<__OUT__
polled ${TEST_NAME}.1 failed at unknown-time
__OUT__
#-------------------------------------------------------------------------------
exit
