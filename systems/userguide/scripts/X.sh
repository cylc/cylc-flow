#!/bin/bash

# CYLC USERGUIDE EXAMPLE SYSTEM,
# Task to get real time obs data for the atmospheric model.

# Run length 5 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

# START MESSAGE
cylc message --started

# check environment
check-env.sh || exit 1

# EXECUTE THE TASK ...
sleep $(( 5 * 60 / $REAL_TIME_ACCEL ))

# "find" the external data and report it available
touch $TMPDIR/obs-${CYCLE_TIME}.nc
cylc message "obs data ready for $CYCLE_TIME"

# SUCCESS MESSAGE
cylc message --succeeded
