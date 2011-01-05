#!/bin/bash

set -e

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $A_INPUT_DIR ]]; then
    echo "ERROR: \$A_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $A_OUTPUT_DIR ]]; then
    echo "ERROR: \$A_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $A_INPUT_DIR ]]; then
    echo "ERROR: \$A_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
ONE=$A_INPUT_DIR/obs-${CYCLE_TIME}.nc
TWO=$A_INPUT_DIR/A-${CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from task $TASK_NAME"

# EXECUTE THE MODEL ...
sleep 10

# generate a restart file for the next cycle
NEXT_CYCLE=$(cylcutil cycle-time -a 6)
touch $A_OUTPUT_DIR/A-${NEXT_CYCLE}.restart

# generate forecast outputs
touch $A_OUTPUT_DIR/surface-winds-${CYCLE_TIME}.nc
touch $A_OUTPUT_DIR/precipitation-${CYCLE_TIME}.nc
