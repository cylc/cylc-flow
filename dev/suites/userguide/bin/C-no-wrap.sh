#!/bin/bash

set -e; trap 'cylc task-failed "error trapped"' ERR

cylc task-started

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d C_INPUT_DIR
cylc checkvars -c C_OUTPUT_DIR C_RUNNING_DIR

# CHECK INPUT FILES EXIST
ONE=$C_INPUT_DIR/precipitation-${CYCLE_TIME}.nc
TWO=$C_RUNNING_DIR/C-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        cylc task-failed "ERROR, file not found $PRE"
        exit 1
    fi
done

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

sleep $TASK_EXE_SECONDS

# generate a restart file for the next three cycles
touch $C_RUNNING_DIR/C-$(cylc cycletime --add=6 ).restart
touch $C_RUNNING_DIR/C-$(cylc cycletime --add=12).restart
touch $C_RUNNING_DIR/C-$(cylc cycletime --add=18).restart

# model outputs
touch $C_OUTPUT_DIR/river-flow-${CYCLE_TIME}.nc

cylc task-message "river flow outputs done for $CYCLE_TIME"

sleep $TASK_EXE_SECONDS

echo "Goodbye"

cylc task-finished
