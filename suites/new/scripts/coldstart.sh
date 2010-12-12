#!/bin/bash

set -e

echo "Hello from task $TASK_NAME"

# EXECUTE THE TASK ...
sleep 10

touch $CYLC_TMPDIR/A-${CYCLE_TIME}.restart
cylc task-message "A restart files ready for $CYCLE_TIME"
touch $CYLC_TMPDIR/B-${CYCLE_TIME}.restart
cylc task-message "B restart files ready for $CYCLE_TIME"
touch $CYLC_TMPDIR/C-${CYCLE_TIME}.restart
cylc task-message "C restart files ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc task-finished
