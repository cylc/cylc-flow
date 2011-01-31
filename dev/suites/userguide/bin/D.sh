#!/bin/bash

cute checkvars  TASK_EXE_SECONDS
cute checkvars -d D_INPUT_DIR
cute checkvars -c D_OUTPUT_DIR

# CHECK INPUT FILES EXIST
ONE=$D_INPUT_DIR/sea-state-${CYCLE_TIME}.nc
TWO=$D_INPUT_DIR/river-flow-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $D_OUTPUT_DIR/combined.products
