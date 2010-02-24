#!/bin/bash

# cylc example system, task F
# depends on task C

# run length 50 minutes

cylc message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 50 * 60 / ACCEL )) 

# check prerequistes
PRE=$TMPDIR/postproc/input/$CYCLE_TIME/forecast.nc
[[ ! -f $PRE ]] && {
    MSG="file not found: $PRE"
    echo "ERROR, postproc: $MSG"
    cylc message -p CRITICAL $MSG
    cylc message -p CRITICAL failed
    exit 1
}

sleep $SLEEP 

OUTDIR=$TMPDIR/postproc/output/$CYCLE_TIME
mkdir -p $OUTDIR
touch $OUTDIR/products.nc
cylc message "forecast products ready for $CYCLE_TIME"

cylc message finished
