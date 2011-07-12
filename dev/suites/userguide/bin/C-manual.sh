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
        cylc task message -p CRITICAL "ERROR, file not found $PRE"
        exit 1
    fi
done

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

#sleep $TASK_EXE_SECONDS

# generate a restart file for the next three cycles
N6=$(cylc cycletime --add=6)
N12=$(cylc cycletime --add=12)
N18=$(cylc cycletime --add=18)

sleep 2
touch $C_RUNNING_DIR/C-${N6}.restart
cylc task message "restart files done for $N6"

sleep 2
touch $C_RUNNING_DIR/C-${N12}.restart
cylc task message "restart files done for $N12"

sleep 2
touch $C_RUNNING_DIR/C-${N18}.restart
cylc task message "restart files done for $N18"

sleep 4

# model outputs
touch $C_OUTPUT_DIR/river-flow-${CYCLE_TIME}.nc

# token output, not used:
cylc task message "river flow outputs done for $CYCLE_TIME"

sleep $TASK_EXE_SECONDS

echo "Goodbye"
cylc task succeeded
