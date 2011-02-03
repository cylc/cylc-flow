#!/bin/bash

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c RUNNING_DIR

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLSUITE_NAME"
sleep $TASK_EXE_SECONDS

touch $RUNNING_DIR/C-${CYCLE_TIME}.restart
