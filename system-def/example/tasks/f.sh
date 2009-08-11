#!/bin/bash

# sequenz example system
# task f
# depends on task c

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PREREQ=$TMPDIR/c.${REFERENCE_TIME}
[[ ! -f $PREREQ ]] && {
    echo "ERROR, file not found: $PREREQ"
    exit 1
}

# generate outputs
touch $TMPDIR/f.${REFERENCE_TIME}
