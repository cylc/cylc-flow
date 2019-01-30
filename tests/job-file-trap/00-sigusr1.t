#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
# Test handle of SIGUSR1. (Handle a mock job vacation.)
# Obviously, job vacation does not happen with background job, and the job
# will no longer be poll-able after the kill.
. $(dirname $0)/test_header

run_tests() {
    set_test_number 6
    install_suite $TEST_NAME_BASE $TEST_NAME_BASE
    TEST_NAME=$TEST_NAME_BASE-validate
    run_ok $TEST_NAME cylc validate $SUITE_NAME
    TEST_NAME=$TEST_NAME_BASE-run
    # Needs to be detaching:
    suite_run_ok $TEST_NAME cylc run --reference-test $SUITE_NAME

    # Make sure t1.1.1's status file is in place
    T1_STATUS_FILE=$SUITE_RUN_DIR/log/job/1/t1/01/job.status

    poll '!' test -e "${T1_STATUS_FILE}"
    poll '!' grep 'CYLC_JOB_PID=' "${T1_STATUS_FILE}"

    # Kill the job and see what happens
    T1_PID=$(awk -F= '$1=="CYLC_JOB_PID" {print $2}' "${T1_STATUS_FILE}")
    kill -s USR1 $T1_PID
    while ps $T1_PID 1>/dev/null 2>&1; do
        sleep 1
    done
    run_fail "${TEST_NAME_BASE}-t1-status" grep -q '^CYLC_JOB' "${T1_STATUS_FILE}"
    TIMEOUT=$(($(date +%s) + 120))
    while ! grep -q 'vacated/USR1' $SUITE_RUN_DIR/log/suite/log \
            && (($TIMEOUT > $(date +%s)))
    do
        sleep 1
    done
    TIMEOUT=$(($(date +%s) + 10))

    if ! which sqlite3 > /dev/null; then
        skip 2 "sqlite3 not installed?"
    else
        while ! sqlite3 "${SUITE_RUN_DIR}/log/db" \
                    'SELECT status FROM task_states WHERE name=="t1";' \
                    >"$TEST_NAME-db-t1" 2>/dev/null \
                && (($TIMEOUT > $(date +%s)))
        do
            sleep 1
        done
        grep_ok "^\(submitted\|running\)$" "$TEST_NAME-db-t1"
        # Start the job again and see what happens
        mkdir -p $SUITE_RUN_DIR/work/1/t1/
        touch $SUITE_RUN_DIR/work/1/t1/file # Allow t1 to complete
        $SUITE_RUN_DIR/log/job/1/t1/01/job </dev/null >/dev/null 2>&1 &
        # Wait for suite to complete
        TIMEOUT=$(($(date +%s) + 120))
        while [[ -f "${SUITE_RUN_DIR}/.service/contact" ]] && (($TIMEOUT > $(date +%s))); do
            sleep 1
        done
        # Test t1 status in DB
        sqlite3 "${SUITE_RUN_DIR}/log/db" \
            'SELECT status FROM task_states WHERE name=="t1";' >"$TEST_NAME-db-t1"
        cmp_ok "$TEST_NAME-db-t1" - <<<'succeeded'
        # Test reference
        TIMEOUT=$(($(date +%s) + 120))
        while ! grep -q 'DONE' "${SUITE_RUN_DIR}/log/suite/log" \
                && (($TIMEOUT > $(date +%s)))
        do
            sleep 1
        done
    fi
    grep_ok 'SUITE REFERENCE TEST PASSED' "${SUITE_RUN_DIR}/log/suite/log"
    purge_suite $SUITE_NAME
    exit
}

# Programs running in some environment is unable to trap SIGUSR1. E.g.:
# An environment documented in this comment:
# https://github.com/cylc/cylc/pull/1648#issuecomment-149348410
trap 'run_tests' 'SIGUSR1'
kill -s 'SIGUSR1' "$$"
sleep 1
skip_all 'Program not receiving SIGUSR1'
