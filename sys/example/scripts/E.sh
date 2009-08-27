#!/bin/bash

# cyclon example system, task E
# depends on task B

# check prerequistes
PRE=$TMPDIR/B.${REFERENCE_TIME}
[[ ! -f $PRE ]] && {
    echo "ERROR, file not found: $PRE"
    exit 1
}

# generate outputs
touch $TMPDIR/E.${REFERENCE_TIME}
