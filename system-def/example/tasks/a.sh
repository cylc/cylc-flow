#!/bin/bash

# cycon example system
# task a
# depends on task z

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PREREQ=$TMPDIR/z.${REFERENCE_TIME}
[[ ! -f $PREREQ ]] && {
    echo "ERROR, file not found: $PREREQ"
    exit 1
}

# generate outputs
touch $TMPDIR/a.${REFERENCE_TIME}.1
touch $TMPDIR/a.${REFERENCE_TIME}.2
