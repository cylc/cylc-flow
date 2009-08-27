#!/bin/bash

# cyclon example system, task ext
# gets external data
# no prerequisites

# generate outputs
touch $TMPDIR/ext.${REFERENCE_TIME}
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME external data ready for $REFERENCE_TIME
