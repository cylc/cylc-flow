#!/bin/bash

# cyclon example system, task F
# depends on task C

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PRE=$TMPDIR/C.${REFERENCE_TIME}
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

# generate outputs
touch $TMPDIR/F.${REFERENCE_TIME}
