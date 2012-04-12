#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c OUTPUT_DIR

echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"
sleep $TASK_EXE_SECONDS

if [[ ! -z $TEST_X_FAIL_TIME ]]; then
    # THIS IS REQUIRED BY THE SCHEDULER TEST SCRIPT
    if [[ $TEST_X_FAIL_TIME = $CYLC_TASK_CYCLE_TIME ]]; then
        echo "ABORTING SUITE BY REQUEST (\$TEST_X_FAIL_TIME)!" >&2
        exit 1
    fi
fi

touch $OUTPUT_DIR/obs-${CYLC_TASK_CYCLE_TIME}.nc
