#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d C_INPUT_DIR
cylc checkvars -c C_OUTPUT_DIR C_RUNNING_DIR

# CHECK INPUT FILES EXIST
ONE=$C_INPUT_DIR/precipitation-${CYCLE_TIME}.nc
TWO=$C_RUNNING_DIR/C-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

if [[ $CYCLE_TIME == $FAIL_CYCLE_TIME ]]; then
    echo "ARRRRRGH!"
    exit 1
fi

sleep $TASK_EXE_SECONDS

# generate a restart file for the next three cycles
touch $C_RUNNING_DIR/C-$(cylc cycletime --add=6 ).restart
touch $C_RUNNING_DIR/C-$(cylc cycletime --add=12).restart
touch $C_RUNNING_DIR/C-$(cylc cycletime --add=18).restart

# model outputs
touch $C_OUTPUT_DIR/river-flow-${CYCLE_TIME}.nc

echo "Goodbye"
