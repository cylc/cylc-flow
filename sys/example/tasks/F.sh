#!/bin/bash

# cyclon example system, task F
# depends on task C

# check prerequistes
PRE=$TMPDIR/C.${REFERENCE_TIME}
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

# generate outputs
touch $TMPDIR/F.${REFERENCE_TIME}
