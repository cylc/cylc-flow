#!/bin/bash

# cyclon example system, task A
# depends on task ext and its own restart file.

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
ONE=$TMPDIR/ext.${REFERENCE_TIME}
TWO=$TMPDIR/A.${REFERENCE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

# generate outputs
touch $TMPDIR/A.${REFERENCE_TIME}.1
touch $TMPDIR/A.${REFERENCE_TIME}.2
touch $TMPDIR/A.${NEXT_REFERENCE_TIME}.restart
