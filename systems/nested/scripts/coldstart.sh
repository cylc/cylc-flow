#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM. 
# system cold start task, provides initial restart prerequisites
# for the forecast models.

# run length 50 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# EXECUTE THE TASK ...
sleep $(( 50 * 60 / $REAL_TIME_ACCEL )) 

touch $TMPDIR/A-${CYCLE_TIME}.restart
cylc message "A restart files ready for $CYCLE_TIME"
touch $TMPDIR/B-${CYCLE_TIME}.restart
cylc message "B restart files ready for $CYCLE_TIME"
touch $TMPDIR/C-${CYCLE_TIME}.restart
cylc message "C restart files ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
