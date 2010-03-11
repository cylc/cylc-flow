#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# system cold start task, provides initial restart prerequisites
# for the forecast models.

# run length 10 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

# EXECUTE THE TASK ...
sleep $SLEEP 

touch $TMPDIR/A-${CYCLE_TIME}.restart
cylc message "A restart files ready for $CYCLE_TIME"
touch $TMPDIR/B-${CYCLE_TIME}.restart
cylc message "B restart files ready for $CYCLE_TIME"
touch $TMPDIR/C-${CYCLE_TIME}.restart
cylc message "C restart files ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
