#!/bin/bash

TMPDIR=${TMPDIR:-/tmp/$USER/sequenz-example}
mkdir -p $TMPDIR

# check prerequistes
[[ ! -f $TMPDIR/A_${REFERENCE_TIME}-1.out ]] && {
    echo "prerequisite not found"
    exit 1
}

# generate outputs
touch $TMPDIR/B_${REFERENCE_TIME}-1.out
touch $TMPDIR/B_${REFERENCE_TIME}-2.out
