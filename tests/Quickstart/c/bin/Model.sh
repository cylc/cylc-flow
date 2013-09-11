#!/bin/bash

set -e

usage() {
    echo "USAGE, $0 [--coldstart]" >&2
}

cylc checkvars  TASK_EXE_SECONDS
cylc checkvars -d MODEL_INPUT_DIR
cylc checkvars -c MODEL_OUTPUT_DIR MODEL_RUNNING_DIR

# CHECK COMMANDLINE
if [[ $# > 1 ]]; then
    usage
    exit 1
elif [[ $# == 1 ]];then
    if [[ $1 == --coldstart ]]; then
        COLDSTART=true
    else
        usage
        exit 1
    fi
else
    COLDSTART=false
fi
 
echo "Hello from $CYLC_TASK_NAME at $CYLC_TASK_CYCLE_TIME in $CYLC_SUITE_REG_NAME"
sleep $TASK_EXE_SECONDS

if $COLDSTART; then
    # just generate a restart file for this cycle
    touch $MODEL_RUNNING_DIR/A-${CYLC_TASK_CYCLE_TIME}.restart
    echo "Goodbye"
    exit 0
fi

# CHECK INPUT FILES EXIST
ONE=$MODEL_INPUT_DIR/obs-${CYLC_TASK_CYCLE_TIME}.nc
TWO=$MODEL_RUNNING_DIR/A-${CYLC_TASK_CYCLE_TIME}.restart
for PRE in $ONE $TWO; do
    if [[ ! -f $PRE ]]; then
        echo "ERROR, file not found $PRE" >&2
        exit 1
    fi
done

# generate a restart file for the next three cycles
touch $MODEL_RUNNING_DIR/A-$(cylc cycletime --offset-hours=6 ).restart
touch $MODEL_RUNNING_DIR/A-$(cylc cycletime --offset-hours=12).restart
touch $MODEL_RUNNING_DIR/A-$(cylc cycletime --offset-hours=18).restart

# model outputs
touch $MODEL_OUTPUT_DIR/surface-winds-${CYLC_TASK_CYCLE_TIME}.nc
touch $MODEL_OUTPUT_DIR/precipitation-${CYLC_TASK_CYCLE_TIME}.nc

echo "Goodbye"
