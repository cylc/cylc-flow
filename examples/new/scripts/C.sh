#!/bin/bash

set -e

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $C_INPUT_DIR ]]; then
    echo "ERROR: \$C_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $C_OUTPUT_DIR ]]; then
    echo "ERROR: \$C_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $C_INPUT_DIR ]]; then
    echo "ERROR: \$C_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
ONE=$C_INPUT_DIR/precipitation-${CYCLE_TIME}.nc
TWO=$C_INPUT_DIR/A-${CYCLE_TIME}.restart
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
touch $C_OUTPUT_DIR/A-${NEXT_CYCLE}.restart

# generate forecast outputs
touch $C_OUTPUT_DIR/river-flow-${CYCLE_TIME}.nc
