#!/bin/bash

# cyclon example system, task cold
# one off cold start task
# generates restart files for task A
# no prerequisites

# run length 10 minutes

task-message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

touch $TMPDIR/A_${REFERENCE_TIME}.restart
task-message A restart files ready for $REFERENCE_TIME

touch $TMPDIR/B_${REFERENCE_TIME}.restart
task-message B restart files ready for $REFERENCE_TIME

touch $TMPDIR/C_${REFERENCE_TIME}.restart
task-message C restart files ready for $REFERENCE_TIME

task-message finished
