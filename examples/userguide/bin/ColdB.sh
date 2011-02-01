#!/bin/bash

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c B_RUNNING_DIR

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"
sleep $TASK_EXE_SECONDS

touch $B_RUNNING_DIR/B-${CYCLE_TIME}.restart
