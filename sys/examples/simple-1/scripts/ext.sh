#!/bin/bash

# cylc example system, task ext
# gets external data
# no prerequisites

# run length 10 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

touch $TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
