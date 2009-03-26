#!/bin/bash

# check prerequistes
[[ ! -f $TMPDIR/A_${REFERENCE_TIME}-1.out ]] && {
    echo "prerequisite not found"
    exit 1
}
[[ ! -f $TMPDIR/B_${REFERENCE_TIME}-2.out ]] && {
    echo "prerequisite not found"
    exit 1
}

# generate outputs
touch $TMPDIR/C_${REFERENCE_TIME}-1.out
touch $TMPDIR/C_${REFERENCE_TIME}-2.out
