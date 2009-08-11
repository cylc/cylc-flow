#!/bin/bash

# cycon example system
# task b
# depends on task a

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PREREQ=$TMPDIR/a.${REFERENCE_TIME}.1
[[ ! -f $PREREQ ]] && {
    echo "ERROR, file not found: $PREREQ"
    exit 1
}

# generate outputs
touch $TMPDIR/b.${REFERENCE_TIME}
