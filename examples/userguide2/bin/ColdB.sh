#!/bin/bash

set -e

# CHECK OUTPUT DIRS ARE DEFINED
if [[ -z $B_OUTPUT_DIR ]]; then
    echo "ERROR: \$B_OUTPUT_DIR is not defined" >&2
    exit 1
fi

mkdir -p $B_OUTPUT_DIR

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

touch $B_OUTPUT_DIR/B-${CYCLE_TIME}.restart
###cylc task-message "B restart files ready for $CYCLE_TIME"
