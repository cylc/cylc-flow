#!/bin/bash

# cylc example system, task cold
# one off cold start task
# generates restart files for forecast
# no prerequisites

# run length 10 minutes

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

RUNDIR=$TMPDIR/forecast/running/$CYCLE_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc message "forecast restart files ready for $CYCLE_TIME"

cylc message --succeeded
