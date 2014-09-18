#!/bin/bash

set -eu

# CHECK INPUT FILES EXIST
PRE=$INPUT_DIR/sea-state-${CYLC_TASK_CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $OUTPUT_DIR/sea-state.products
