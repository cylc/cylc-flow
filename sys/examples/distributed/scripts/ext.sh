#!/bin/bash

# cylc example system, task ext
# gets external data
# no prerequisites

# run length 10 minutes

cylc message started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

OUTDIR=$TMPDIR/$TASK_NAME/output/$CYCLE_TIME
mkdir -p $OUTDIR
touch $OUTDIR/extdata

cylc message external data ready for $CYCLE_TIME
cylc message finished
