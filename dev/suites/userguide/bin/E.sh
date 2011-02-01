#!/bin/bash

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d E_INPUT_DIR
cylc checkvars -c E_OUTPUT_DIR

# CHECK INPUT FILES EXIST
PRE=$E_INPUT_DIR/sea-state-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $E_OUTPUT_DIR/sea-state.products
