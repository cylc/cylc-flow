#!/bin/bash

cute checkvars  TASK_EXE_SECONDS
cute checkvars -c C_RUNNING_DIR

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"
sleep $TASK_EXE_SECONDS

touch $C_RUNNING_DIR/C-${CYCLE_TIME}.restart
