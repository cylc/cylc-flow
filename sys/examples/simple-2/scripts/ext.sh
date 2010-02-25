#!/bin/bash

# cylc example system, task ext
# gets external data
# no prerequisites

# run length 10 minutes

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

#echo $TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
touch $TMPDIR/${TASK_NAME}_${CYCLE_TIME}.output
cylc message "external data ready for $CYCLE_TIME"

cylc message --succeeded
