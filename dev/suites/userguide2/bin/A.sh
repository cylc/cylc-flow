#!/bin/bash

cylcutil checkvars  TASK_EXE_SECONDS
cylcutil checkvars -d A_INPUT_DIR
cylcutil checkvars -c A_OUTPUT_DIR A_RUNNING_DIR

# CHECK INPUT FILES EXIST
ONE=$A_INPUT_DIR/obs-${CYCLE_TIME}.nc
TWO=$A_RUNNING_DIR/A-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"
sleep $TASK_EXE_SECONDS

# generate a restart file for the next three cycles
touch $A_RUNNING_DIR/A-$(cylcutil cycletime --add=6 ).restart
touch $A_RUNNING_DIR/A-$(cylcutil cycletime --add=12).restart
touch $A_RUNNING_DIR/A-$(cylcutil cycletime --add=18).restart

# model outputs
touch $A_OUTPUT_DIR/surface-winds-${CYCLE_TIME}.nc
touch $A_OUTPUT_DIR/precipitation-${CYCLE_TIME}.nc

echo "Goodbye"
