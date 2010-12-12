#!/bin/bash

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $F_INPUT_DIR ]]; then
    echo "ERROR: \$F_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $F_OUTPUT_DIR ]]; then
    echo "ERROR: \$F_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $F_INPUT_DIR ]]; then
    echo "ERROR: \$F_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
PRE=$F_INPUT_DIR/river-flow-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from task $TASK_NAME"

# EXECUTE THE MODEL ...
sleep 10

# generate outputs
touch $F_OUTPUT_DIR/river-flow.products
