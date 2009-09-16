#!/bin/bash

# cyclon example system, task ext
# gets external data
# no prerequisites

# run length 10 minutes

task-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

touch $TMPDIR/${TASK_NAME}_${REFERENCE_TIME}.output
task-message external data ready for $REFERENCE_TIME

task-message finished
