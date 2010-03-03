#!/bin/bash

# cylc example system, task ext
# gets external data
# no prerequisites

# run length 10 minutes

cylc message --started

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

sleep $SLEEP 

OUTDIR=$TMPDIR/$CYLC_TASK/output/$CYLC_TIME
mkdir -p $OUTDIR
touch $OUTDIR/extdata

cylc message "external data ready for $CYLC_TIME"
cylc message --succeeded
