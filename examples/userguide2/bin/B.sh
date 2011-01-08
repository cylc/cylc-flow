#!/bin/bash

set -e

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $B_INPUT_DIR ]]; then
    echo "ERROR: \$B_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $B_OUTPUT_DIR ]]; then
    echo "ERROR: \$B_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $B_INPUT_DIR ]]; then
    echo "ERROR: \$B_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
ONE=$B_INPUT_DIR/surface-winds-${CYCLE_TIME}.nc
TWO=$B_INPUT_DIR/A-${CYCLE_TIME}.restart
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
touch $B_OUTPUT_DIR/A-${NEXT_CYCLE}.restart

# generate forecast output
touch $B_OUTPUT_DIR/sea-state-${CYCLE_TIME}.nc
