#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d INPUT_DIR
cylc checkvars -c OUTPUT_DIR RUNNING_DIR

# CHECK INPUT FILES EXIST
ONE=$INPUT_DIR/surface-winds-${CYLC_TASK_CYCLE_TIME}.nc
TWO=$RUNNING_DIR/B-${CYLC_TASK_CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"

sleep $TASK_EXE_SECONDS

# generate a restart file for the next and T+24 cycles
touch $RUNNING_DIR/B-$(cylc cycletime --offset-hours=6 ).restart
touch $RUNNING_DIR/B-$(cylc cycletime --offset-hours=24).restart

# model outputs
touch $OUTPUT_DIR/sea-state-${CYLC_TASK_CYCLE_TIME}.nc

echo "Goodbye"
