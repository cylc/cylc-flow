#!/bin/bash

# cyclon example system, task C
# depends on task A and its own restart file

# check prerequistes
ONE=$TMPDIR/A.${REFERENCE_TIME}.2
TWO=$TMPDIR/C.${REFERENCE_TIME}.restart
for PRE in $ONE $TWO; do
    [[ ! -f $PRE ]] && {
        echo "ERROR, file not found: $PRE"
        exit 1
    }
done

# ARTIFICIAL ERROR
[[ $REFERENCE_TIME == 2009082512 ]] && {
    echo "C: ERROR!!!!!!"
    exit 1
}

# generate outputs
touch $TMPDIR/C.${REFERENCE_TIME}
touch $TMPDIR/C.${NEXT_REFERENCE_TIME}.restart
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME $TASK_NAME restart files ready for $NEXT_REFERENCE_TIME
touch $TMPDIR/C.${NEXT_NEXT_REFERENCE_TIME}.restart
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME $TASK_NAME restart files ready for $NEXT_NEXT_REFERENCE_TIME
