#!/bin/bash

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $E_INPUT_DIR ]]; then
    echo "ERROR: \$E_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $E_OUTPUT_DIR ]]; then
    echo "ERROR: \$E_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $E_INPUT_DIR ]]; then
    echo "ERROR: \$E_INPUT_DIR not found" >&2
    exit 1
fi

# CHECK PREREQUISITES
PRE=$E_INPUT_DIR/sea-state-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from task $TASK_NAME"

# EXECUTE THE MODEL ...
sleep 10

# generate outputs
touch $E_OUTPUT_DIR/sea-state.products
