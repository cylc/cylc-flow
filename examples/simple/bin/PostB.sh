#!/bin/bash

cute checkvars  TASK_EXE_SECONDS
cute checkvars -d POSTB_INPUT_DIR
cute checkvars -c POSTB_OUTPUT_DIR

# CHECK INPUT FILES EXIST
PRE=$POSTB_INPUT_DIR/precipitation-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $POSTB_OUTPUT_DIR/precip.products
