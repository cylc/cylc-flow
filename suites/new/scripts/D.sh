#!/bin/bash

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $D_INPUT_DIR ]]; then
    echo "ERROR: \$D_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $D_OUTPUT_DIR ]]; then
    echo "ERROR: \$D_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $D_INPUT_DIR ]]; then
    echo "ERROR: \$D_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
ONE=$C_INPUT_DIR/sea-state-${CYCLE_TIME}.nc
TWO=$C_INPUT_DIR/river-flow-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

echo "Hello from task $TASK_NAME"

# EXECUTE THE MODEL ...
sleep 10

# generate outputs
touch $D_OUTPUT_DIR/combined.products
