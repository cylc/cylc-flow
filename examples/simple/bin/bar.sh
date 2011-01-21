#!/bin/bash

if [[ -z $BAR_INPUT_DIR ]]; then
    echo "ERROR: \$BAR_INPUT_DIR is not defined" >&2
    exit 1
fi
if [[ -z $BAR_OUTPUT_DIR ]]; then
    echo "ERROR: \$BAR_OUTPUT_DIR is not defined" >&2
    exit 1
fi
if [[ ! -d $BAR_INPUT_DIR ]]; then
    echo "ERROR: \$BAR_INPUT_DIR not found" >&2
    exit 1
fi

# execution time may be set in suite.rc
TASK_EXE_SECONDS=${TASK_EXE_SECONDS:-10}

mkdir -p $BAR_OUTPUT_DIR

PRE=$BAR_INPUT_DIR/data.$CYCLE_TIME
if [[ ! -f $PRE ]]; then
    echo "ERROR, file not found $PRE" >&2
    exit 1
fi

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

sleep $TASK_EXE_SECONDS

touch $BAR_OUTPUT_DIR/products.$CYCLE_TIME

echo "Goodbye"
