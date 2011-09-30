#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c RUNNING_DIR

echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"
sleep $TASK_EXE_SECONDS

touch $RUNNING_DIR/A-${CYLC_TASK_CYCLE_TIME}.restart
