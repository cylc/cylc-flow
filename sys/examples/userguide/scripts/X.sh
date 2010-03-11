#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM,
# Task to get real time obs data for the atmospheric model.

# Run length 10 minutes, scaled.

# START MESSAGE
cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

# EXECUTE THE TASK ...
sleep $SLEEP 

# "find" the external data and report it available
touch $TMPDIR/obs-${CYCLE_TIME}.nc
cylc message "obs data ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
