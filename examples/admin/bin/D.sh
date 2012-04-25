#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d INPUT_DIR
cylc checkvars -c OUTPUT_DIR

# CHECK INPUT FILES EXIST
ONE=$INPUT_DIR/sea-state-${CYLC_TASK_CYCLE_TIME}.nc
TWO=$INPUT_DIR/river-flow-${CYLC_TASK_CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $OUTPUT_DIR/combined.products
