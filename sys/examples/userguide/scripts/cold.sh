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

touch $TMPDIR/atmos-${CYLC_TIME}.restart
cylc message "atmos restart files ready for $CYLC_TIME"
touch $TMPDIR/sea-state-${CYLC_TIME}.restart
cylc message "sea_state restart files ready for $CYLC_TIME"
touch $TMPDIR/storm-surge-${CYLC_TIME}.restart
cylc message "storm_surge restart files ready for $CYLC_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
