#!/bin/bash

cute checkvars  TASK_EXE_SECONDS
cute checkvars -d POSTA_INPUT_DIR
cute checkvars -c POSTA_OUTPUT_DIR

# CHECK INPUT FILES EXIST
PRE=$POSTA_INPUT_DIR/surface-winds-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

sleep $TASK_EXE_SECONDS

# generate outputs
touch $POSTA_OUTPUT_DIR/surface-wind.products
