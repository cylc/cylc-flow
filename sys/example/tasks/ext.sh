#!/bin/bash

# cyclon example system, task ext
# gets external data
# no prerequisites

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# generate outputs
touch $TMPDIR/ext.${REFERENCE_TIME}
