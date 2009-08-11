#!/bin/bash

# cycon example system
# task e
# depends on task b

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PREREQ=$TMPDIR/b.${REFERENCE_TIME}
[[ ! -f $PREREQ ]] && {
    echo "ERROR, file not found: $PREREQ"
    exit 1
}

# generate outputs
touch $TMPDIR/e.${REFERENCE_TIME}
