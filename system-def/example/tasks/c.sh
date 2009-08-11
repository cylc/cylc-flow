#!/bin/bash

# cycon example system
# task c
# depends on task a

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PREREQ=$TMPDIR/a.${REFERENCE_TIME}.2
[[ ! -f $PREREQ ]] && {
    echo "ERROR, file not found: $PREREQ"
    exit 1
}

# generate outputs
touch $TMPDIR/c.${REFERENCE_TIME}
