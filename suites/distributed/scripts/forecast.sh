#!/bin/bash

# cylc example suite, task forecast
# depends on task ext and its own restart file.

# run length 10 minutes, one restart file

cylc task-started || exit 1

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL ))

# check prerequistes
ONE=$CYLC_REMOTE_TMPDIR/input/$CYCLE_TIME/extdata
TWO=$CYLC_REMOTE_TMPDIR/running/$CYCLE_TIME/restart
echo $ONE
ls $ONE
echo $TWO
ls $TWO

for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        MSG="file not found: $PRE"
        echo "ERROR, forecast: $MSG"
        cylc task-failed $MSG
        exit 1
    }
done

sleep $SLEEP # 90 min

RUNDIR=$CYLC_REMOTE_TMPDIR/running/$NEXT_CYCLE_TIME
mkdir -p $RUNDIR
touch $RUNDIR/restart
cylc task-message --next-restart-completed

OUTDIR=$CYLC_REMOTE_TMPDIR/output/$CYCLE_TIME
mkdir -p $OUTDIR
touch $OUTDIR/forecast.nc
cylc task-message "forecast output ready for $CYCLE_TIME"

cylc task-finished
