#!/bin/bash

set -e; trap 'cylc task-failed "error trapped"' ERR

# to simulate stuck in queue for 10 seconds:
# sleep 10

# START MESSAGE
cylc task-started || exit 1

# the err trap gets failures here:
cute checkvars  TASK_EXE_SECONDS
cute checkvars -d D_INPUT_DIR
cute checkvars -c D_OUTPUT_DIR

# CHECK INPUT FILES EXIST
ONE=$D_INPUT_DIR/sea-state-${CYCLE_TIME}.nc
TWO=$D_INPUT_DIR/river-flow-${CYCLE_TIME}.nc
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        # FAILED MESSAGE
        cylc task-failed "file not found: $PRE"
        exit 1
    fi
done

echo "Hello from $TASK_NAME at $CYCLE_TIME in $CYLC_SUITE_NAME"

# task task warning hook:
cylc task-message -p WARNING "This is a warning!"

sleep $TASK_EXE_SECONDS
# OR to test task execution timeout:
#sleep 5
#cylc task-message "still alive"
#sleep 5

# generate outputs
touch $D_OUTPUT_DIR/combined.products

# SUCCESS MESSAGE
cylc task-finished
