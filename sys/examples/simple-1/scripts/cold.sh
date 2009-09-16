#!/bin/bash

# cyclon example system, task cold
# one off cold start task
# generates restart files for task A
# no prerequisites

# run length 10 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

touch $TMPDIR/A_${REFERENCE_TIME}.restart
touch $TMPDIR/B_${REFERENCE_TIME}.restart
touch $TMPDIR/C_${REFERENCE_TIME}.restart
