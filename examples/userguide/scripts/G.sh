#!/bin/bash

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $G_INPUT_DIR ]]; then
    echo "ERROR: \$G_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $G_OUTPUT_DIR ]]; then
    echo "ERROR: \$G_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $G_INPUT_DIR ]]; then
    echo "ERROR: \$G_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
PRE=$G_INPUT_DIR/river-flow-products-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from task $TASK_NAME"

# EXECUTE THE MODEL ...
sleep 10

# generate outputs
touch $G_OUTPUT_DIR/processed-river-flow-products.nc
