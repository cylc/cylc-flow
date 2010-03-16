#!/bin/bash

# cylc file-move example system, task ext
# gets external data
# no prerequisites

# run length 10 minutes

cylc message --started

# check environment
check-env.sh || exit 1

sleep $(( 10 * 60 / REAL_TIME_ACCEL )) 

OUTDIR=$TMPDIR/$TASK_NAME/output/$CYCLE_TIME
mkdir -p $OUTDIR
touch $OUTDIR/extdata

cylc message "external data ready for $CYCLE_TIME"

cylc message --succeeded
