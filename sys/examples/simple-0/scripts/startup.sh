#!/bin/bash

# cylon example system, task startup
# one off initial task to clean the example system working directory
# no prerequisites

# run length 10 minutes

ACCEL=$(( 3600 / 10 )) # 10 s => 1 hour
SLEEP=$(( 10 * 60 / ACCEL )) 

mkdir -p $TMPDIR || exit 1

sleep $SLEEP 

echo "Cleaning $TMPDIR"
rm -rf $TMPDIR/* || exit 1

echo "Creating initial restart files for A, B, C"
touch $TMPDIR/A_${REFERENCE_TIME}.restart
touch $TMPDIR/B_${REFERENCE_TIME}.restart
touch $TMPDIR/C_${REFERENCE_TIME}.restart
