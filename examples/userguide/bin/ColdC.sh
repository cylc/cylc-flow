#!/bin/bash

set -e

# CHECK OUTPUT DIRS ARE DEFINED
if [[ -z $C_OUTPUT_DIR ]]; then
    echo "ERROR: \$C_OUTPUT_DIR is not defined" >&2
    exit 1
fi

mkdir -p $C_OUTPUT_DIR

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

touch $C_OUTPUT_DIR/C-${CYCLE_TIME}.restart
###cylc task-message "C restart files ready for $CYCLE_TIME"
