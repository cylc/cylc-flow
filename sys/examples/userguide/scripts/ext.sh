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
touch $TMPDIR/atmos-obs-${CYLC_TIME}.nc
cylc message "atmospheric observations ready for $CYLC_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
