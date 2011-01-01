#!/bin/bash

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc task-failed "error trapped"' ERR

# START MESSAGE
cylc task-started || exit 1

# CHECK INPUT AND OUTPUT DIRS ARE DEFINED
if [[ -z $F_INPUT_DIR ]]; then
    cylc task-failed "ERROR: \$F_INPUT_DIR is not defined"
    exit 1
fi
if [[ -z $F_OUTPUT_DIR ]]; then
    cylc task-failed "ERROR: \$F_OUTPUT_DIR is not defined"
    exit 1
fi
if [[ ! -d $F_INPUT_DIR ]]; then
    cylc task-failed "ERROR: \$F_INPUT_DIR not found"
    exit 1
fi

# CHECK PREREQUISITES
PRE=$F_INPUT_DIR/river-flow-${CYCLE_TIME}.nc
if [[ ! -f $PRE ]]; then
    cylc task-failed "ERROR, file not found $PRE"
    exit 1
fi

echo "Hello from task $TASK_NAME"

# EXECUTE THE MODEL ...
sleep 10

# generate outputs
touch $F_OUTPUT_DIR/river-flow-products-${CYCLE_TIME}.nc
cylc task-message "foo products ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
