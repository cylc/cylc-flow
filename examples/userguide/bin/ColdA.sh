#!/bin/bash

set -e

# CHECK OUTPUT DIRS ARE DEFINED
if [[ -z $A_OUTPUT_DIR ]]; then
    echo "ERROR: \$A_OUTPUT_DIR is not defined" >&2
    exit 1
fi
mkdir -p $A_OUTPUT_DIR

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

touch $A_OUTPUT_DIR/A-${CYCLE_TIME}.restart
