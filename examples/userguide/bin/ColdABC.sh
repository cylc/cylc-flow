#!/bin/bash

set -e

# CHECK OUTPUT DIRS ARE DEFINED
if [[ -z $A_OUTPUT_DIR ]]; then
    echo "ERROR: \$A_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $B_OUTPUT_DIR ]]; then
    echo "ERROR: \$B_OUTPUT_DIR is not defined" >&2
    exit 1
fi

if [[ -z $C_OUTPUT_DIR ]]; then
    echo "ERROR: \$C_OUTPUT_DIR is not defined" >&2
    exit 1
fi

mkdir -p $A_OUTPUT_DIR $B_OUTPUT_DIR $C_OUTPUT_DIR

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

touch $A_OUTPUT_DIR/A-${CYCLE_TIME}.restart
###cylc task-message "A restart files ready for $CYCLE_TIME"
touch $B_OUTPUT_DIR/B-${CYCLE_TIME}.restart
###cylc task-message "B restart files ready for $CYCLE_TIME"
touch $C_OUTPUT_DIR/C-${CYCLE_TIME}.restart
###cylc task-message "C restart files ready for $CYCLE_TIME"

#### SUCCESS MESSAGE
###cylc task-finished
