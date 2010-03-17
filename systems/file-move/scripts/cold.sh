#!/bin/bash

# cylc file-move example system, oneoff coldstart task
# generates restart files for forecast
# no prerequisites

# run length 10 minutes, scaled by $REAL_TIME_ACCEL 

# trap errors so that we need not check the success of basic operations.
set -e; trap 'cylc message --failed' ERR

cylc message --started

# check environment
check-env.sh || exit 1

sleep $(( 10 * 60 / REAL_TIME_ACCEL )) 

RUNDIR=$TMPDIR/forecast/running/$CYCLE_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc message "forecast restart files ready for $CYCLE_TIME"

cylc message --succeeded
