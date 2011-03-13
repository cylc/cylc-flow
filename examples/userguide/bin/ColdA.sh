#!/bin/bash

set -e

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -c RUNNING_DIR

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE"
sleep $TASK_EXE_SECONDS

touch $RUNNING_DIR/A-${CYCLE_TIME}.restart
