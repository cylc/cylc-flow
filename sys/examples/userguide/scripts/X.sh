#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM,
# Task to get real time obs data for the atmospheric model.

# Run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# START MESSAGE
cylc message --started

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

# "find" the external data and report it available
touch $TMPDIR/obs-${CYCLE_TIME}.nc
cylc message "obs data ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
