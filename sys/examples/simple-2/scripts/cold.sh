#!/bin/bash

# cylc example system, task cold
# one off cold start task
# generates restart files for task A
# no prerequisites

# run length 10 minutes

cylc message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

touch $TMPDIR/A_${CYCLE_TIME}.restart
cylc message A restart files ready for $CYCLE_TIME

touch $TMPDIR/B_${CYCLE_TIME}.restart
cylc message B restart files ready for $CYCLE_TIME

touch $TMPDIR/C_${CYCLE_TIME}.restart
cylc message C restart files ready for $CYCLE_TIME

cylc message finished
