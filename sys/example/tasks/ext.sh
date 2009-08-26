#!/bin/bash

# cyclon example system, task ext
# gets external data
# no prerequisites

TMPDIR=${TMPDIR:-/tmp/$USER/example}
mkdir -p $TMPDIR

# generate outputs
touch $TMPDIR/ext.${REFERENCE_TIME}
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME external data ready for $REFERENCE_TIME
