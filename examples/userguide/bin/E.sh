#!/bin/bash

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d INPUT_DIR
cylc checkvars -c OUTPUT_DIR

# CHECK INPUT FILES EXIST
PRE=$INPUT_DIR/sea-state-${CYCLETIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from $TASK_NAME at $CYCLETIME in $CYLC_SUITNAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $OUTPUT_DIR/sea-state.products
