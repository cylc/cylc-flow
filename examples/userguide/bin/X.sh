#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c OUTPUT_DIR

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE"
sleep $TASK_EXE_SECONDS

echo "XXXXXXXXXXX $TEST_X_FAIL_TIME"
if [[ ! -z $TEST_X_FAIL_TIME ]]; then
    # required by the scheduler test script
    if [[ $TEST_X_FAIL_TIME = $CYCLE_TIME ]]; then
        echo "ABORTING BY SUITE OWNER REQUEST!"
        exit 1
    fi
fi

touch $OUTPUT_DIR/obs-${CYCLE_TIME}.nc
