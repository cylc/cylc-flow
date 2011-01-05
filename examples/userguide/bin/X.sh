#!/bin/bash

set -e

# CHECK OUTPUT DIR IS DEFINED
if [[ -z $X_OUTPUT_DIR ]]; then
    echo "ERROR: \$X_OUTPUT_DIR is not defined" >&2
    exit 1
fi

mkdir -p $X_OUTPUT_DIR

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

# "find" the external data and report it available
touch $X_OUTPUT_DIR/obs-${CYCLE_TIME}.nc
