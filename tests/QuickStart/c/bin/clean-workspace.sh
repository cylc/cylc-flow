#!/bin/bash

set -e

usage="USAGE: clean-workspace.sh PATH"

if [[ $# != 1 ]]; then
    echo $usage >&2
    exit 1
fi

# execution time may be set in suite.rc
TASK_EXE_SECONDS=${TASK_EXE_SECONDS:-10}

echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"

sleep $TASK_EXE_SECONDS

if [[ $# == 1 ]]; then
    WORKSPACE=$1
else
    echo "No workspace specified for cleaning"
    exit 1
fi

echo "Cleaning $WORKSPACE ..."

rm -rf $WORKSPACE
mkdir -p $WORKSPACE

echo "Done"
