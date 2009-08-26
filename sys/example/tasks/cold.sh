#!/bin/bash

# cyclon example system, task cold
# one off cold start task
# generates restart files for task A
# no prerequisites

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# generate outputs
touch $TMPDIR/A.${REFERENCE_TIME}.restart
