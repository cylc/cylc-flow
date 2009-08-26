#!/bin/bash

# cyclon example system, task D
# depends on tasks B and C

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
ONE=$TMPDIR/B.${REFERENCE_TIME}
TWO=$TMPDIR/C.${REFERENCE_TIME}
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

# generate outputs
touch $TMPDIR/D.${REFERENCE_TIME}
