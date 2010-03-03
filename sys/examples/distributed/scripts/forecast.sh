#!/bin/bash

# cylc example system, task forecast
# depends on task ext and its own restart file.

# run length 10 minutes, one restart file

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL ))

# check prerequistes
ONE=/tmp/oliverh/forecast/input/$CYLC_TIME/extdata
TWO=/tmp/oliverh/forecast/running/$CYLC_TIME/restart
echo $ONE
ls $ONE
echo $TWO
ls $TWO

for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, forecast: $MSG"
        cylc message -p CRITICAL $MSG
        cylc message --failed
        exit 1
    }
done

sleep $SLEEP # 90 min

RUNDIR=/tmp/oliverh/forecast/running/$NEXT_CYLC_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc message "$CYLC_TASK restart files ready for $NEXT_CYLC_TIME"

OUTDIR=/tmp/oliverh/forecast/output/$CYLC_TIME
mkdir -p $OUTDIR
touch $OUTDIR/forecast.nc
cylc message "forecast output ready for $CYLC_TIME"

cylc message --succeeded
