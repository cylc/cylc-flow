#!/bin/bash

# cycon example system
# task d
# depends on tasks b and c

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# check prerequistes
PREREQS="$TMPDIR/b.${REFERENCE_TIME} $TMPDIR/c.${REFERENCE_TIME}"
for PREREQ in $PREREQS; do
    [[ ! -f $PREREQ ]] && {
        echo "ERROR, file not found: $PREREQ"
        exit 1
    }
done

# generate outputs
touch $TMPDIR/d.${REFERENCE_TIME}
