#!/bin/bash

# cyclon example system, task cold
# one off cold start task
# generates restart files for task A
# no prerequisites

# generate outputs
touch $TMPDIR/A.${REFERENCE_TIME}.restart
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME A restart files ready for $REFERENCE_TIME
touch $TMPDIR/B.${REFERENCE_TIME}.restart
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME B restart files ready for $REFERENCE_TIME
touch $TMPDIR/C.${REFERENCE_TIME}.restart
task-message -p NORMAL -n $TASK_NAME -r $REFERENCE_TIME C restart files ready for $REFERENCE_TIME
