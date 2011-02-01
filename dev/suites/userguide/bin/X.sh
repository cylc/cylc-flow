#!/bin/bash

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c X_OUTPUT_DIR

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"
sleep $TASK_EXE_SECONDS

touch $X_OUTPUT_DIR/obs-${CYCLE_TIME}.nc
