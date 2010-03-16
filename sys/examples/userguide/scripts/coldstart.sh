#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# system cold start task, provides initial restart prerequisites
# for the forecast models.

# run length 50 minutes, scaled by $REAL_TIME_ACCEL 

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# EXECUTE THE TASK ...
sleep $(( 50 * 60 / REAL_TIME_ACCEL )) 

touch $TMPDIR/A-${CYCLE_TIME}.restart
cylc message "A restart files ready for $CYCLE_TIME"
touch $TMPDIR/B-${CYCLE_TIME}.restart
cylc message "B restart files ready for $CYCLE_TIME"
touch $TMPDIR/C-${CYCLE_TIME}.restart
cylc message "C restart files ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
