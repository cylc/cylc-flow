#!/bin/bash

# initial task (no prerequistes)

TMPDIR=${TMPDIR:-/tmp/$USER/sequenz-example}
mkdir -p $TMPDIR

# generate outputs
touch $TMPDIR/A_${REFERENCE_TIME}-1.out
touch $TMPDIR/A_${REFERENCE_TIME}-2.out
