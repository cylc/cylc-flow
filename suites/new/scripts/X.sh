#!/bin/bash

set -e

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $X_INPUT_DIR ]]; then
    echo "ERROR: \$X_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $X_OUTPUT_DIR ]]; then
    echo "ERROR: \$X_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $X_INPUT_DIR ]]; then
    echo "ERROR: \$X_INPUT_DIR not found" >&2
    exit 1
fi

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

# "find" the external data and report it available
touch $X_OUTPUT_DIR/obs-${CYCLE_TIME}.nc
